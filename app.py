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
import base64
import cv2 # چشم جمشید
import numpy as np
import random

# --- چک کردن ابزار تدوین ---
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
            system_msg = "تو نویسنده خلاق یوتیوب هستی. زیرنویس را به سناریوی جذاب فارسی تبدیل کن (۳ بخش متوالی). لحن: صمیمی و داستان‌گو."
        else:
            system_msg = "تو تحلیلگر هستی. جان کلام متن را استخراج کن."

        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": f"متن ورودی:\n{text[:15000]}"}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e: return f"خطای OpenAI: {e}"

# >>> تابع جدید: استخراج فریم از یوتیوب <<<
def capture_frames_from_youtube(video_url, num_frames=6):
    """دانلود موقت ویدئو و شکار ۶ فریم رندم"""
    video_path = "temp_capture.mp4"
    try:
        # 1. دانلود با کمترین کیفیت (برای سرعت)
        ydl_opts = {
            'format': 'worst[ext=mp4]', # کیفیت پایین کافیه
            'outtmpl': video_path,
            'quiet': True,
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # 2. باز کردن ویدئو با OpenCV
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 3. انتخاب ۶ فریم تصادفی (با فاصله از ابتدا و انتها)
        margin = total_frames // 10
        random_indices = sorted(random.sample(range(margin, total_frames - margin), num_frames))
        
        frames_bytes = []
        for idx in random_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                # تبدیل به فرمت قابل ارسال (JPG Bytes)
                _, buffer = cv2.imencode('.jpg', frame)
                frames_bytes.append(buffer.tobytes())
        
        cap.release()
        os.remove(video_path) # پاک کردن فایل موقت
        return frames_bytes
        
    except Exception as e:
        if os.path.exists(video_path): os.remove(video_path)
        return str(e)

def analyze_and_generate_mix(img1_bytes, img2_bytes):
    try:
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])
        b64_img1 = base64.b64encode(img1_bytes).decode('utf-8')
        b64_img2 = base64.b64encode(img2_bytes).decode('utf-8')
        
        vision_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an art director. Create a DALL-E 3 prompt based on these two TV show screenshots."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Combine these two scenes into one artistic composition description. Focus on characters and mood. Style: Pastel Painting, Cinematic, 16:9 Aspect Ratio. No Text."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img1}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img2}"}}
                ]}
            ], max_tokens=150
        )
        mix_prompt = vision_response.choices[0].message.content
        
        image_response = client.images.generate(
            model="dall-e-3", prompt=f"{mix_prompt}. Aspect Ratio 16:9. Style: Pastel Painting.",
            size="1792x1024", quality="standard", n=1
        )
        return image_response.data[0].url, mix_prompt
    except Exception as e: return None, str(e)

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
            "text": safe_text, "model_id": "eleven_multilingual_v2", 
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200: return response.content, None
        else: return None, response.text
    except Exception as e: return None, str(e)

# --- توابع کمکی ---
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

# --- UI ---
st.title("👑 اتاق فرمان جمشید")
tab_news, tab_story, tab_sound, tab_art, tab_montage, tab_config = st.tabs(["📰 اخبار", "✍️ سناریو", "🎙️ صدا", "🎨 گالری (خودکار)", "🎬 تدوین", "⚙️ تنظیمات"])

# تب ۱: اخبار
with tab_news:
    if st.button("🔄 بروزرسانی"):
        ws_conf = sh.worksheet("Config")
        new_news = []
        for item in ws_conf.get_all_records():
            if item['Type'] == 'RSS' and item['Value']: new_news.extend(fetch_rss_feed(item['Value']))
        if new_news:
            sh.worksheet("News_Feed").append_rows([n + [""] for n in new_news])
            st.success("اخبار جدید!")
            st.rerun()
    try: st.dataframe(pd.DataFrame(sh.worksheet("News_Feed").get_all_records()), use_container_width=True)
    except: pass

# تب ۲: سناریو
with tab_story:
    with st.form("story"):
        c1, c2 = st.columns([3, 1])
        v_url = c1.text_input("لینک یوتیوب:")
        manual = c1.text_area("متن دستی:", height=100)
        p_name = c2.text_input("نام پروژه:")
        voice_dict = get_elevenlabs_voices()
        idx = list(voice_dict.keys()).index("Nima (VIP)") if "Nima (VIP)" in voice_dict else 0
        v_name = c2.selectbox("صدا:", list(voice_dict.keys()), index=idx)
        if st.form_submit_button("ثبت"):
            txt = manual if manual else (download_transcript_heavy(v_url) if v_url else "")
            vid = voice_dict.get(v_name, "")
            if txt:
                sh.worksheet("Video_Factory").append_row([p_name, v_url, txt, "", vid, "Raw", ""])
                st.success("ثبت شد.")
            else: st.error("خطا.")
    st.divider()
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df = pd.DataFrame(ws_vid.get_all_records())
        if not df.empty:
            pend = df.reset_index()
            idx = st.selectbox("انتخاب پروژه:", pend.index, format_func=lambda x: pend.loc[x, 'Project_Name'])
            row = pend.loc[idx]
            style = st.radio("سبک:", ["پاورقی", "جان کلام"], horizontal=True)
            if st.button("✨ نوشتن"):
                res = generate_script_gpt(row['Subtitle_Text'], style)
                cell = ws_vid.find(row['Project_Name'])
                ws_vid.update_cell(cell.row, 4, res)
                st.success("نوشته شد.")
    except: pass

# تب ۳: صدا
with tab_sound:
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df = pd.DataFrame(ws_vid.get_all_records())
        if not df.empty:
            rdy = df[df['Script'] != ""].reset_index()
            if not rdy.empty:
                idx = st.selectbox("پروژه صوتی:", rdy.index, format_func=lambda x: rdy.loc[x, 'Project_Name'])
                row = rdy.loc[idx]
                txt = st.text_area("متن نهایی:", row['Script'], height=150)
                if st.button("🎙️ تولید"):
                    aud, err = generate_audio_v3(txt, row['Voice_ID'])
                    if aud: st.audio(aud); st.success("دانلود کنید.")
                    else: st.error(err)
    except: pass

# --- تب ۴: گالری (تمام اتوماتیک) ---
with tab_art:
    st.header("۳. آتلیه نقاشی خودکار 🎨")
    st.caption("جمشید خودش به یوتیوب می‌رود، ۶ عکس شکار می‌کند و ۳ پوستر می‌کشد.")
    
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df_vid = pd.DataFrame(ws_vid.get_all_records())
        if not df_vid.empty:
            ready_art = df_vid[df_vid['Script'] != ""].reset_index()
            
            if not ready_art.empty:
                sel_idx_art = st.selectbox("انتخاب پروژه برای عکاسی و نقاشی:", ready_art.index, format_func=lambda x: f"{ready_art.loc[x, 'Project_Name']}")
                row_art = ready_art.loc[sel_idx_art]
                video_link = row_art['Youtube_Link']
                
                if st.button("📸 شکار صحنه و شروع نقاشی (Auto)"):
                    if not video_link:
                        st.error("لینک یوتیوب در این پروژه موجود نیست.")
                    else:
                        status = st.status("در حال عملیات...", expanded=True)
                        
                        # گام ۱: دانلود و شکار فریم
                        status.write("1️⃣ در حال دانلود ویدئو و شکار فریم‌ها...")
                        frames = capture_frames_from_youtube(video_link, num_frames=6)
                        
                        if isinstance(frames, str): # اگر ارور باشد، متن ارور است
                            status.update(label="خطا در دانلود", state="error")
                            st.error(f"مشکل دانلود: {frames}")
                        else:
                            status.write("✅ ۶ فریم شکار شد. شروع ترکیب و نقاشی...")
                            
                            # نمایش فریم‌های شکار شده (اختیاری - برای جذابیت)
                            st.image(frames, caption=[f"Frame {i+1}" for i in range(6)], width=150)
                            
                            # گام ۲: تولید تصاویر
                            pairs = [(frames[0], frames[1]), (frames[2], frames[3]), (frames[4], frames[5])]
                            cols = st.columns(3)
                            
                            for i, (img1, img2) in enumerate(pairs):
                                with cols[i]:
                                    with st.spinner(f"نقاشی پوستر {i+1}..."):
                                        url, _ = analyze_and_generate_mix(img1, img2)
                                        if url:
                                            st.image(url, caption=f"پوستر {i+1}", use_container_width=True)
                                            st.markdown(f"[⬇️ دانلود]({url})")
                            
                            status.update(label="عملیات موفق! 🎉", state="complete", expanded=False)
            else: st.info("پروژه آماده نداریم.")
    except: pass

# تب ۵: تدوین
with tab_montage:
    if HAS_MOVIEPY:
        img = st.file_uploader("تصویر:", type=["jpg","png"])
        aud = st.file_uploader("صدا:", type=["mp3"])
        if img and aud and st.button("🎬 رندر"):
            with open("t.jpg","wb") as f: f.write(img.getbuffer())
            with open("t.mp3","wb") as f: f.write(aud.getbuffer())
            ac = AudioFileClip("t.mp3")
            vc = ImageClip("t.jpg").set_duration(ac.duration).set_audio(ac)
            vc.write_videofile("o.mp4", fps=24, codec="libx264", audio_codec="aac")
            st.video("o.mp4")
            with open("o.mp4","rb") as f: st.download_button("⬇️", f, "video.mp4")
    else: st.warning("نصب نیست.")

with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
