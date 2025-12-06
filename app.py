import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import feedparser
import yt_dlp
from openai import OpenAI
import requests
from datetime import datetime
import os

# --- تلاش برای وارد کردن ابزار تدوین (جلوگیری از کرش کردن کل برنامه) ---
try:
    from moviepy.editor import ImageClip, AudioFileClip
    HAS_MOVIEPY = True
except ImportError:
    HAS_MOVIEPY = False

st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

# --- 1. اتصال به دیتابیس ---
@st.cache_resource
def connect_to_db():
    try:
        info = dict(st.secrets["gcp_service_account"]).copy()
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open("Command_Center")
    except Exception as e:
        st.error(f"❌ خطای دیتابیس: {e}")
        st.stop()

sh = connect_to_db()

# --- 2. توابع هوشمند ---
def generate_script_gpt(text, project_type):
    if not text: return "متنی وجود ندارد."
    try:
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])
        if project_type == "پاورقی (سریال ترکی)":
            system_msg = "تو نویسنده خلاق یوتیوب هستی. زیرنویس را به سناریوی جذاب فارسی تبدیل کن (۳ بخش متوالی)."
        else:
            system_msg = "تو تحلیلگر هستی. جان کلام متن را استخراج کن."

        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": f"متن ورودی:\n{text[:15000]}"}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e: return f"خطای OpenAI: {e}"

def get_elevenlabs_voices():
    voices = {"Nima (VIP)": "ZHv32fN3Y8F0CxAiAoLA"}
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": st.secrets["elevenlabs"]["api_key"]}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            api_voices = {v['name']: v['voice_id'] for v in response.json()['voices']}
            voices.update(api_voices)
    except: pass
    return voices

def generate_audio_v3(text, voice_id):
    try:
        safe_text = text[:2900] 
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": st.secrets["elevenlabs"]["api_key"], "Content-Type": "application/json"}
        data = {
            "text": safe_text,
            "model_id": "eleven_multilingual_v2", 
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200: return response.content, None
        else: return None, response.text
    except Exception as e: return None, str(e)

# --- 3. توابع کمکی ---
def fetch_rss_feed(rss_url):
    try:
        feed = feedparser.parse(rss_url)
        return [[datetime.now().strftime("%Y-%m-%d %H:%M"), feed.feed.get('title', 'Unknown'), entry.title, entry.link, "New"] for entry in feed.entries[:5]]
    except: return []

def download_transcript_heavy(url):
    try:
        ydl_opts = {'skip_download': True, 'writesubtitles': True, 'writeautomaticsub': True, 'subtitleslangs': ['fa','en','tr'], 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'subtitles' in info and info['subtitles']: return "زیرنویس رسمی یافت شد."
            if 'automatic_captions' in info: return "زیرنویس اتوماتیک یافت شد."
        return None
    except: return None

# --- 4. رابط کاربری ---
st.title("👑 اتاق فرمان جمشید")
tab_news, tab_story, tab_sound, tab_montage, tab_config = st.tabs([
    "📰 اتاق خبر", 
    "✍️ استودیو سناریو", 
    "🎙️ کارخانه صدا", 
    "🎬 میز تدوین",
    "⚙️ تنظیمات"
])

# --- تب ۱: اخبار ---
with tab_news:
    if st.button("🔄 بروزرسانی اخبار"):
        ws_conf = sh.worksheet("Config")
        new_news = []
        for item in ws_conf.get_all_records():
            if item['Type'] == 'RSS' and item['Value']:
                new_news.extend(fetch_rss_feed(item['Value']))
        if new_news:
            sh.worksheet("News_Feed").append_rows([n + [""] for n in new_news])
            st.success("اخبار جدید رسید!")
            st.rerun()
    try: st.dataframe(pd.DataFrame(sh.worksheet("News_Feed").get_all_records()), use_container_width=True)
    except: pass

# --- تب ۲: استودیو سناریو ---
with tab_story:
    st.header("۱. ورودی و نگارش")
    with st.form("story_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            v_url = st.text_input("لینک یوتیوب:")
            manual = st.text_area("متن دستی (زیرنویس خام):", height=100)
        with col2:
            p_name = st.text_input("نام پروژه:")
            voice_dict = get_elevenlabs_voices()
            idx_nima = list(voice_dict.keys()).index("Nima (VIP)") if "Nima (VIP)" in voice_dict else 0
            voice_name = st.selectbox("گوینده پیش‌فرض:", list(voice_dict.keys()), index=idx_nima)

        if st.form_submit_button("ثبت ورودی"):
            sub_text = manual if manual else (download_transcript_heavy(v_url) if v_url else "")
            final_voice_id = voice_dict.get(voice_name, "")
            if sub_text:
                fname = p_name if p_name.strip() else f"Project {datetime.now().strftime('%H%M')}"
                sh.worksheet("Video_Factory").append_row([fname, v_url, sub_text, "", final_voice_id, "Raw", ""])
                st.success("ثبت شد!")
                st.rerun()
            else: st.error("متن/لینک نامعتبر.")

    st.divider()
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df_vid = pd.DataFrame(ws_vid.get_all_records())
        if not df_vid.empty:
            pending = df_vid.reset_index()
            def get_label(x): return f"{pending.loc[x, 'Project_Name']}"
            sel_idx = st.selectbox("انتخاب پروژه برای نوشتن:", pending.index, format_func=get_label)
            sel_row = pending.loc[sel_idx]
            
            st.info(f"پروژه: {sel_row['Project_Name']}")
            style = st.radio("سبک نوشتن:", ["پاورقی (سریال ترکی)", "جان کلام"], horizontal=True)
            
            if st.button("✨ نوشتن سناریو (GPT)"):
                with st.spinner("نویسنده در حال کار..."):
                    res = generate_script_gpt(sel_row['Subtitle_Text'], style)
                    if "خطا" not in res:
                        cell = ws_vid.find(sel_row['Project_Name'])
                        ws_vid.update_cell(cell.row, 4, res)
                        ws_vid.update_cell(cell.row, 6, "Script Ready")
                        st.success("سناریو نوشته شد!")
                        st.rerun()
                    else: st.error(res)
    except: pass

# --- تب ۳: کارخانه صدا ---
with tab_sound:
    st.header("۲. ویرایش و تولید صدا")
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df_vid = pd.DataFrame(ws_vid.get_all_records())
        if not df_vid.empty:
            ready_for_audio = df_vid[df_vid['Script'] != ""].reset_index()
            if not ready_for_audio.empty:
                def get_lbl_aud(x): return f"{ready_for_audio.loc[x, 'Project_Name']}"
                sel_idx_aud = st.selectbox("انتخاب پروژه برای صدا:", ready_for_audio.index, format_func=get_lbl_aud)
                row_aud = ready_for_audio.loc[sel_idx_aud]
                
                edited_script = st.text_area("متن نهایی:", value=row_aud['Script'], height=200)
                
                if st.button("🎙️ تولید صدا"):
                    vid_voice = row_aud['Voice_ID']
                    if not vid_voice: st.error("آیدی صدا ندارد.")
                    else:
                        with st.spinner("ضبط صدا..."):
                            if edited_script != row_aud['Script']:
                                cell = ws_vid.find(row_aud['Project_Name'])
                                ws_vid.update_cell(cell.row, 4, edited_script)
                            
                            audio_data, err = generate_audio_v3(edited_script, vid_voice)
                            if audio_data:
                                st.audio(audio_data, format='audio/mp3')
                                st.success("تولید شد! دانلود کنید ⬇️")
                            else: st.error(err)
            else: st.info("پروژه آماده صدا نداریم.")
    except: pass

# --- تب ۴: میز تدوین (امن) ---
with tab_montage:
    st.header("۳. ترکیب صدا و تصویر")
    
    if HAS_MOVIEPY:
        col_img, col_aud = st.columns(2)
        with col_img:
            uploaded_img = st.file_uploader("۱. تصویر:", type=["jpg", "png"])
        with col_aud:
            uploaded_audio = st.file_uploader("۲. صدا:", type=["mp3"])
            
        if uploaded_img and uploaded_audio:
            if st.button("🎬 رندر ویدئو"):
                with st.spinner("در حال ساخت ویدئو..."):
                    try:
                        with open("temp_img.jpg", "wb") as f: f.write(uploaded_img.getbuffer())
                        with open("temp_audio.mp3", "wb") as f: f.write(uploaded_audio.getbuffer())
                        
                        audio_clip = AudioFileClip("temp_audio.mp3")
                        video_clip = ImageClip("temp_img.jpg").set_duration(audio_clip.duration)
                        video_clip = video_clip.set_audio(audio_clip)
                        video_clip.write_videofile("final_output.mp4", fps=1, codec="libx264", audio_codec="aac")
                        
                        st.video("final_output.mp4")
                        with open("final_output.mp4", "rb") as file:
                            st.download_button("⬇️ دانلود نهایی", file, "video.mp4")
                            
                        os.remove("temp_img.jpg")
                        os.remove("temp_audio.mp3")
                        os.remove("final_output.mp4")
                        
                    except Exception as e:
                        st.error(f"خطا در رندر: {e}")
    else:
        st.warning("⚠️ ابزار تدوین (moviepy) هنوز روی سرور نصب نشده است.")
        st.info("راه حل: لطفاً یک بار دیگر در پنل Streamlit دکمه Reboot App را بزنید تا فایل requirements.txt جدید خوانده شود.")

with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
