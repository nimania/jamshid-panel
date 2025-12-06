import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import feedparser
import yt_dlp
from openai import OpenAI
import requests
import json
from datetime import datetime

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
            system_msg = "تو یک نویسنده خلاق هستی. متن زیرنویس را به یک سناریوی جذاب و داستان‌گو برای یوتیوب تبدیل کن. سه بخش متوالی."
        else:
            system_msg = "تو یک تحلیلگر هستی. جان کلام متن زیر را استخراج کن."

        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": f"متن ورودی:\n{text[:15000]}"}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e: return f"خطای OpenAI: {e}"

def get_elevenlabs_voices():
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": st.secrets["elevenlabs"]["api_key"]}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return {v['name']: v['voice_id'] for v in response.json()['voices']}
        return {}
    except: return {}

def generate_audio(text, voice_id):
    try:
        # برای تست اولیه، فقط ۱۰۰۰ کاراکتر اول را می‌فرستیم تا اگر متن طولانی بود ارور ندهد
        safe_text = text[:1000] 
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": st.secrets["elevenlabs"]["api_key"],
            "Content-Type": "application/json"
        }
        data = {
            "text": safe_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            return response.content, None
        else:
            # برگرداندن متن دقیق خطا برای عیب‌یابی
            return None, response.text
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
tab_news, tab_video, tab_config = st.tabs(["📰 اتاق خبر", "🎬 کارخانه ویدئو", "⚙️ تنظیمات"])

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

with tab_video:
    st.header("۱. ورودی")
    with st.form("input_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            v_url = st.text_input("لینک یوتیوب:")
            manual = st.text_area("متن دستی:", height=100)
        with col2:
            p_name = st.text_input("نام پروژه:")
            p_type = st.selectbox("نوع:", ["پاورقی (سریال ترکی)", "جان کلام (تحلیلی)"])
            
            # دریافت لیست صداها
            voice_dict = get_elevenlabs_voices()
            voice_options = list(voice_dict.keys())
            
            # انتخاب‌گر صدا با قابلیت جستجو
            selected_voice_name = st.selectbox("انتخاب صدا از لیست:", ["انتخاب کنید..."] + voice_options)
            
            # کادر برای آیدی دستی (اگر در لیست نبود)
            manual_voice_id = st.text_input("یا Voice ID را دستی وارد کنید (اگر در لیست نیست):")

        if st.form_submit_button("ثبت"):
            sub_text = manual if manual else (download_transcript_heavy(v_url) if v_url else "")
            
            # اولویت با آیدی دستی است، بعد لیست
            final_voice_id = manual_voice_id if manual_voice_id else voice_dict.get(selected_voice_name, "")
            
            if sub_text:
                final_name = p_name if p_name.strip() else f"پروژه {datetime.now().strftime('%H:%M:%S')}"
                sh.worksheet("Video_Factory").append_row([final_name, v_url, sub_text, "", final_voice_id, "Ready for AI", ""])
                st.success(f"ثبت شد! (Voice ID: {final_voice_id})")
                st.rerun()
            else: st.error("متن یا لینک معتبر وارد کنید.")

    st.divider()
    st.header("۲. استودیو تولید (متن و صدا)")
    
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df_vid = pd.DataFrame(ws_vid.get_all_records())
        
        if not df_vid.empty:
            pending = df_vid.reset_index()
            def get_label(x):
                return f"{pending.loc[x, 'Project_Name']} | {pending.loc[x, 'Status']}"

            sel_idx = st.selectbox("انتخاب پروژه:", pending.index, format_func=get_label)
            sel_row = pending.loc[sel_idx]
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.subheader("نوشتن سناریو")
                override_type = st.radio("سبک:", ["پاورقی (سریال ترکی)", "جان کلام"], horizontal=True)
                if st.button("✨ نوشتن (GPT)"):
                    with st.spinner("نوشتن..."):
                        res = generate_script_gpt(sel_row['Subtitle_Text'], override_type)
                        if "خطا" not in res:
                            cell = ws_vid.find(sel_row['Project_Name'])
                            ws_vid.update_cell(cell.row, 4, res)
                            ws_vid.update_cell(cell.row, 6, "Script Done")
                            st.success("نوشته شد!")
                            st.rerun()
                        else: st.error(res)
            
            with col_b:
                st.subheader("تولید صدا")
                script_content = sel_row['Script']
                saved_voice_id = sel_row['Voice_ID']
                
                st.caption(f"Voice ID استفاده شده: {saved_voice_id}")
                
                if script_content:
                    if st.button("🎙️ تست تولید صدا (۱۰۰۰ حرف اول)"):
                        if not saved_voice_id:
                            st.error("آیدی صدا نداریم. دستی وارد کنید یا پروژه را ویرایش کنید.")
                        else:
                            with st.spinner("ارسال به ElevenLabs..."):
                                audio_bytes, error_msg = generate_audio(script_content, saved_voice_id)
                                if audio_bytes:
                                    st.audio(audio_bytes, format='audio/mp3')
                                    st.success("صدا با موفقیت تولید شد! ✅")
                                else:
                                    st.error("خطا از طرف ElevenLabs:")
                                    st.code(error_msg) # نمایش دقیق متن خطا
                else:
                    st.info("اول سناریو را بنویسید.")
        st.dataframe(df_vid, use_container_width=True)
    except Exception as e: st.write(f"وضعیت: {e}")

with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
