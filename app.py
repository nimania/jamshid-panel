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
import cv2 
import numpy as np
import random
import time

# --- تنظیمات اولیه ---
st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

# چک کردن ابزار تدوین
try:
    from moviepy.editor import ImageClip, AudioFileClip
    HAS_MOVIEPY = True
except ImportError:
    HAS_MOVIEPY = False

# --- مدیریت ناوبری هوشمند ---
if 'active_step' not in st.session_state:
    st.session_state.active_step = "News Room"

def go_to(step_name):
    st.session_state.active_step = step_name
    st.rerun()

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

def capture_frames_from_youtube(video_url, num_frames=6):
    video_path = "temp_capture.mp4"
    try:
        ydl_opts = {'format': 'worst[ext=mp4]', 'outtmpl': video_path, 'quiet': True, 'no_warnings': True,
                    'http_headers': {'User-Agent': 'Mozilla/5.0'}}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([video_url])
        
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 100: return "ویدئو ناقص است."
        
        frames = []
        indices = sorted(random.sample(range(total//10, total - total//10), num_frames))
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                _, buf = cv2.imencode('.jpg', frame)
                frames.append(buf.tobytes())
        cap.release()
        if os.path.exists(video_path): os.remove(video_path)
        return frames
    except Exception as e:
        if os.path.exists(video_path): os.remove(video_path)
        return str(e)

def analyze_and_generate_mix(img1, img2):
    try:
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])
        b1 = base64.b64encode(img1).decode('utf-8')
        b2 = base64.b64encode(img2).decode('utf-8')
        
        vis_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Art director. Merge scenes."},
                {"role": "user", "content": [{"type": "text", "text": "Merge these two TV scenes into one pastel painting poster. 16:9 aspect ratio."}, 
                                             {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b1}"}},
                                             {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b2}"}}]}
            ], max_tokens=150
        )
        prompt = vis_resp.choices[0].message.content
        img_resp = client.images.generate(model="dall-e-3", prompt=f"{prompt}. 16:9 Pastel Style.", size="1792x1024", n=1)
        return img_resp.data[0].url
    except Exception as e: return None

def get_elevenlabs_voices():
    voices = {"Nima (VIP)": "ZHv32fN3Y8F0CxAiAoLA"}
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": st.secrets["elevenlabs"]["api_key"]}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            voices.update({v['name']: v['voice_id'] for v in r.json()['voices']})
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
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
        }
        r = requests.post(url, json=data, headers=headers)
        if r.status_code == 200: return r.content, None
        else: return None, r.text
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

# --- UI: منوی کناری ---
st.title("👑 اتاق فرمان جمشید")

steps = ["News Room", "Scenario Studio", "Sound Factory", "Art Gallery", "Montage Table", "Settings"]
if st.session_state.active_step not in steps: st.session_state.active_step = steps[0]
selected_step = st.sidebar.radio("مراحل تولید:", steps, index=steps.index(st.session_state.active_step))

if selected_step != st.session_state.active_step:
    st.session_state.active_step = selected_step
    st.rerun()

# ----------------- 1. News Room -----------------
if st.session_state.active_step == "News Room":
    st.header("📰 اتاق خبر")
    if st.button("🔄 دریافت اخبار و رفتن به سناریو"):
        ws_conf = sh.worksheet("Config")
        new_news = []
        for item in ws_conf.get_all_records():
            if item['Type'] == 'RSS' and item['Value']: new_news.extend(fetch_rss_feed(item['Value']))
        if new_news:
            sh.worksheet("News_Feed").append_rows([n + [""] for n in new_news])
            st.toast("اخبار دریافت شد!", icon="🚀")
            time.sleep(1)
            go_to("Scenario Studio") 
        else: st.warning("خبر جدیدی نبود.")
    try: st.dataframe(pd.DataFrame(sh.worksheet("News_Feed").get_all_records()), use_container_width=True)
    except: pass

# ----------------- 2. Scenario Studio -----------------
elif st.session_state.active_step == "Scenario Studio":
    st.header("✍️ استودیو سناریو")
    with st.expander("ثبت پروژه جدید", expanded=True):
        c1, c2 = st.columns([3, 1])
        v_url = c1.text_input("لینک یوتیوب:")
        manual = c1.text_area("متن دستی:")
        p_name = c2.text_input("نام پروژه:")
        voice_dict = get_elevenlabs_voices()
        v_name = c2.selectbox("صدا:", list(voice_dict.keys()))
        if st.button("ثبت پروژه"):
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
            last_idx = len(pend) - 1
            idx = st.selectbox("انتخاب پروژه:", pend.index, index=last_idx, format_func=lambda x: pend.loc[x, 'Project_Name'])
            row = pend.loc[idx]
            style = st.radio("سبک:", ["پاورقی", "جان کلام"], horizontal=True)
            if st.button("✨ نوشتن و رفتن به صدا"):
                with st.spinner("نویسنده در حال کار..."):
                    res = generate_script_gpt(row['Subtitle_Text'], style)
                    cell = ws_vid.find(row['Project_Name'])
                    ws_vid.update_cell(cell.row, 4, res)
                    st.toast("سناریو آماده شد!", icon="🎙️")
                    time.sleep(1)
                    go_to("Sound Factory")
    except: pass

# ----------------- 3. Sound Factory -----------------
elif st.session_state.active_step == "Sound Factory":
    st.header("🎙️ کارخانه صدا (V3)")
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df = pd.DataFrame(ws_vid.get_all_records())
        if not df.empty:
            ready = df[df['Script'] != ""].reset_index()
            if not ready.empty:
                last_r_idx = len(ready) - 1
                idx = st.selectbox("پروژه صوتی:", ready.index, index=last_r_idx, format_func=lambda x: ready.loc[x, 'Project_Name'])
                row = ready.loc[idx]
                txt = st.text_area("ویرایش نهایی متن:", row['Script'], height=200)
                if st.button("🎙️ تولید صدا و رفتن به گالری"):
                    with st.spinner("جمشید در حال ضبط (V3)..."):
                        if txt != row['Script']:
                            cell = ws_vid.find(row['Project_Name'])
                            ws_vid.update_cell(cell.row, 4, txt)
                        aud, err = generate_audio_v3(txt, row['Voice_ID'])
                        if aud:
                            st.audio(aud)
                            st.success("صدا تولید شد!")
                            time.sleep(1)
                            go_to("Art Gallery")
                        else: st.error(err)
    except: pass

# ----------------- 4. Art Gallery -----------------
elif st.session_state.active_step == "Art Gallery":
    st.header("🎨 گالری تصاویر")
    mode = st.radio("مود:", ["آپلود دستی (پیشنهادی)", "اتوماتیک"], horizontal=True)
    if mode == "آپلود دستی (پیشنهادی)":
        files = st.file_uploader("۶ تصویر آپلود کنید:", accept_multiple_files=True)
        if files and len(files)==6 and st.button("ترکیب و ساخت پوستر"):
            frames = [f.getvalue() for f in files]
            pairs = [(frames[0], frames[1]), (frames[2], frames[3]), (frames[4], frames[5])]
            cols = st.columns(3)
            for i, (im1, im2) in enumerate(pairs):
                with cols[i]:
                    with st.spinner(f"نقاشی {i+1}..."):
                        url = analyze_and_generate_mix(im1, im2)
                        if url: st.image(url, use_container_width=True); st.markdown(f"[دانلود]({url})")
            st.success("تصاویر آماده شد!")
            if st.button("رفتن به تدوین"): go_to("Montage Table")

# ----------------- 5. Montage Table -----------------
elif st.session_state.active_step == "Montage Table":
    st.header("🎬 میز تدوین")
    if HAS_MOVIEPY:
        img = st.file_uploader("تصویر نهایی:", type=["jpg","png"])
        aud = st.file_uploader("صدا نهایی:", type=["mp3"])
        
        if img and aud:
            if st.button("🎬 رندر نهایی"):
                with st.spinner("در حال رندر ویدئو (لطفا صبر کنید)..."):
                    try:
                        # ذخیره فایل‌ها
                        with open("t.jpg","wb") as f: f.write(img.getbuffer())
                        with open("t.mp3","wb") as f: f.write(aud.getbuffer())
                        
                        # عملیات رندر (بدون لاگر پیچیده برای پایداری)
                        ac = AudioFileClip("t.mp3")
                        vc = ImageClip("t.jpg").set_duration(ac.duration).set_audio(ac)
                        # استفاده از تنظیمات امن برای سرور لینوکس
                        vc.write_videofile("o.mp4", fps=24, codec="libx264", audio_codec="aac")
                        
                        st.success("رندر تمام شد! 🎉")
                        st.video("o.mp4")
                        with open("o.mp4","rb") as f:
                            st.download_button("⬇️ دانلود ویدئو", f, "final_video.mp4")

                        # ارسال به تلگرام
                        st.divider()
                        st.markdown("### ✈️ ارسال به تلگرام")
                        tg_token = st.text_input("Token:")
                        chat_id = st.text_input("Chat ID:")
                        if tg_token and chat_id and st.button("ارسال"):
                            with open("o.mp4", "rb") as video:
                                r = requests.post(f"https://api.telegram.org/bot{tg_token}/sendVideo", 
                                                files={'video': video}, data={'chat_id': chat_id})
                                if r.status_code == 200: st.success("ارسال شد!")
                                else: st.error(r.text)
                    except Exception as e: st.error(f"خطا: {e}")
    else: st.warning("MoviePy نصب نیست.")

# ----------------- 6. Settings -----------------
elif st.session_state.active_step == "Settings":
    st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
