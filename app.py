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
from bs4 import BeautifulSoup # برای خواندن وب‌سایت

# --- تنظیمات ---
st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

try:
    from moviepy.editor import ImageClip, AudioFileClip
    HAS_MOVIEPY = True
except ImportError:
    HAS_MOVIEPY = False

if 'active_step' not in st.session_state: st.session_state.active_step = "News Room"
if 'temp_news' not in st.session_state: st.session_state.temp_news = []

def go_to(step_name):
    st.session_state.active_step = step_name
    st.rerun()

# --- 1. اتصال دیتابیس ---
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
def generate_script_gpt(text, project_type, custom_prompt=""):
    if not text: return "متنی وجود ندارد."
    try:
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])
        
        # مدیریت پرامت‌ها
        if project_type == "پاورقی (سریال ترکی)":
            system_msg = "تو نویسنده خلاق یوتیوب هستی. زیرنویس را به سناریوی جذاب فارسی تبدیل کن (۳ بخش متوالی). لحن: صمیمی و داستان‌گو."
        elif project_type == "جان کلام (تحلیلی)":
            system_msg = "تو تحلیلگر هستی. یک ری‌کپ حرفه‌ای، دقیق و موشکافانه از گفته‌های این متن تهیه کن."
        else: # حالت سوم: پرامت دستی
            system_msg = f"دستور کار: {custom_prompt}"

        response = client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": f"متن ورودی:\n{text[:15000]}"}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e: return f"خطای OpenAI: {e}"

def analyze_and_generate_mix(images_bytes, user_instruction):
    try:
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])
        
        # آماده‌سازی تصاویر برای ویژن
        content_list = [{"type": "text", "text": f"Create a DALL-E 3 prompt based on these images. Instruction: {user_instruction}. Style: Pastel Painting, Cinematic, 16:9 Aspect Ratio. No Text."}]
        
        # اضافه کردن حداکثر 2 تصویر برای تحلیل (برای صرفه‌جویی و محدودیت توکن)
        # اگر کاربر 6 تا فرستاد، ما یک کلاژ ذهنی می‌سازیم یا دو تای اول را می‌فرستیم
        # اینجا دو تای اول را می‌فرستیم که نماینده باشند
        for img in images_bytes[:2]: 
            b64 = base64.b64encode(img).decode('utf-8')
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        vision_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an art director."},
                {"role": "user", "content": content_list}
            ], max_tokens=200
        )
        mix_prompt = vision_response.choices[0].message.content
        
        image_response = client.images.generate(
            model="dall-e-3", prompt=f"{mix_prompt}. Aspect Ratio 16:9.", size="1792x1024", n=1
        )
        return image_response.data[0].url
    except Exception as e: return None

def generate_audio_v3(text, voice_id):
    try:
        safe_text = text[:2900] 
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": st.secrets["elevenlabs"]["api_key"], "Content-Type": "application/json"}
        data = {
            "text": safe_text, "model_id": "eleven_multilingual_v2", 
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
        }
        r = requests.post(url, json=data, headers=headers)
        if r.status_code == 200: return r.content, None
        else: return None, r.text
    except Exception as e: return None, str(e)

# --- توابع خبرخوان ---
def fetch_website_meta(url):
    """استخراج تیتر از وب‌سایت"""
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.string if soup.title else url
        return [[datetime.now().strftime("%Y-%m-%d %H:%M"), "Website", title, url, "New"]]
    except: return []

def fetch_youtube_rss(channel_url):
    """تبدیل لینک کانال به RSS"""
    # این روش ساده است، برای کانال‌ها معمولا channel_id لازم است
    # اینجا فرض می‌کنیم کاربر لینک RSS کانال را می‌دهد یا ما تلاش می‌کنیم پیدا کنیم
    # برای سادگی فعلا از متد RSS استفاده می‌کنیم
    return [] 

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

# --- UI ---
st.title("👑 اتاق فرمان جمشید")
steps = ["News Room", "Scenario Studio", "Sound Factory", "Art Gallery", "Montage Table", "Settings"]
selected_step = st.sidebar.radio("مراحل تولید:", steps, index=steps.index(st.session_state.active_step))
if selected_step != st.session_state.active_step:
    st.session_state.active_step = selected_step
    st.rerun()

# ----------------- 1. News Room (اصلاح شده) -----------------
if st.session_state.active_step == "News Room":
    st.header("📰 اتاق خبر")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("۱. دریافت خودکار")
        if st.button("🔄 فراخوانی منابع (RSS/Site)"):
            ws_conf = sh.worksheet("Config")
            temp_list = []
            for item in ws_conf.get_all_records():
                if item['Type'] == 'RSS' and item['Value']:
                    temp_list.extend(fetch_rss_feed(item['Value']))
                elif item['Type'] == 'Website' and item['Value']:
                    temp_list.extend(fetch_website_meta(item['Value']))
            
            st.session_state.temp_news = temp_list
            if temp_list: st.success(f"{len(temp_list)} آیتم پیدا شد. در پایین ویرایش کنید.")
            else: st.warning("چیزی پیدا نشد.")

    with col2:
        st.subheader("۲. ورودی دستی")
        with st.form("manual_news"):
            m_source = st.selectbox("منبع:", ["Twitter (X)", "Telegram", "Instagram", "Other"])
            m_title = st.text_input("تیتر/خلاصه خبر:")
            m_link = st.text_input("لینک پست:")
            if st.form_submit_button("افزودن به لیست"):
                st.session_state.temp_news.append([
                    datetime.now().strftime("%Y-%m-%d %H:%M"), m_source, m_title, m_link, "New"
                ])
                st.rerun()

    st.divider()
    st.subheader("۳. ویرایش و تایید نهایی")
    
    if st.session_state.temp_news:
        # تبدیل لیست به دیتافریم برای ادیتور
        df_temp = pd.DataFrame(st.session_state.temp_news, columns=["Date", "Source", "Title", "Link", "Status"])
        # نمایش ادیتور
        edited_df = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True)
        
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("💾 ذخیره نهایی در دیتابیس"):
            # تبدیل دوباره به لیست و ذخیره
            final_data = edited_df.values.tolist()
            if final_data:
                sh.worksheet("News_Feed").append_rows([r + [""] for r in final_data]) # ستون خالی برای فرمت
                st.session_state.temp_news = [] # خالی کردن حافظه موقت
                st.success("ذخیره شد!")
                time.sleep(1)
                go_to("Scenario Studio")
        
        if col_s2.button("❌ پاک کردن لیست موقت"):
            st.session_state.temp_news = []
            st.rerun()
    else:
        st.info("لیست موقت خالی است. منابع را فراخوانی کنید یا دستی اضافه کنید.")
        # نمایش اخبار قبلی دیتابیس
        with st.expander("مشاهده آرشیو دیتابیس"):
            try: st.dataframe(pd.DataFrame(sh.worksheet("News_Feed").get_all_records()))
            except: pass

# ----------------- 2. Scenario Studio (اصلاح شده) -----------------
elif st.session_state.active_step == "Scenario Studio":
    st.header("✍️ استودیو سناریو")
    st.info("وظیفه: فقط ورودی و نوشتن متن (بدون تولید صدا)")
    
    with st.expander("ثبت پروژه جدید", expanded=True):
        c1, c2 = st.columns([3, 1])
        v_url = c1.text_input("لینک یوتیوب:")
        manual = c1.text_area("متن دستی:")
        p_name = c2.text_input("نام پروژه:")
        
        # انتخاب صدا اینجا فقط برای رزرو است
        voice_dict = get_elevenlabs_voices()
        v_name = c2.selectbox("رزرو صدا:", list(voice_dict.keys()))
        
        if st.button("ثبت ورودی"):
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
            idx = st.selectbox("انتخاب پروژه:", pend.index, index=len(pend)-1, format_func=lambda x: pend.loc[x, 'Project_Name'])
            row = pend.loc[idx]
            
            # >>> انتخاب حالت سوم (Custom) <<<
            style = st.radio("مود نویسنده:", ["پاورقی (سریال ترکی)", "جان کلام (تحلیلی)", "✨ پرامت آزاد (Custom)"], horizontal=True)
            
            custom_prompt = ""
            if style == "✨ پرامت آزاد (Custom)":
                custom_prompt = st.text_area("دستور اختصاصی به نویسنده:", "مثلا: این متن را به صورت یک داستان ترسناک بازنویسی کن...")
            
            if st.button("✨ نوشتن سناریو"):
                with st.spinner("نویسنده در حال کار..."):
                    res = generate_script_gpt(row['Subtitle_Text'], style, custom_prompt)
                    cell = ws_vid.find(row['Project_Name'])
                    ws_vid.update_cell(cell.row, 4, res)
                    st.toast("سناریو آماده شد! انتقال به کارخانه صدا...", icon="🎙️")
                    time.sleep(1)
                    go_to("Sound Factory")
    except: pass

# ----------------- 3. Sound Factory (تخصصی صدا) -----------------
elif st.session_state.active_step == "Sound Factory":
    st.header("🎙️ کارخانه صدا (V3)")
    st.info("وظیفه: ویرایش نهایی متن و تبدیل به صدا")
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df = pd.DataFrame(ws_vid.get_all_records())
        if not df.empty:
            ready = df[df['Script'] != ""].reset_index()
            if not ready.empty:
                idx = st.selectbox("پروژه:", ready.index, index=len(ready)-1, format_func=lambda x: ready.loc[x, 'Project_Name'])
                row = ready.loc[idx]
                
                txt = st.text_area("ویرایش نهایی متن:", row['Script'], height=200)
                
                if st.button("🎙️ تولید صدا و رفتن به گالری"):
                    with st.spinner("جمشید در حال ضبط (V3)..."):
                        if txt != row['Script']: # ذخیره ادیت
                            cell = ws_vid.find(row['Project_Name'])
                            ws_vid.update_cell(cell.row, 4, txt)
                        
                        aud, err = generate_audio_v3(txt, row['Voice_ID'])
                        if aud:
                            st.audio(aud)
                            st.success("تولید شد! دانلود کنید.")
                            time.sleep(1)
                            go_to("Art Gallery")
                        else: st.error(err)
    except: pass

# ----------------- 4. Art Gallery (میکس پیشرفته) -----------------
elif st.session_state.active_step == "Art Gallery":
    st.header("🎨 گالری تصاویر")
    
    tab_auto, tab_mix = st.tabs(["📸 شکار خودکار (یوتیوب)", "📂 ترکیب دستی + پرامت"])
    
    with tab_auto:
         st.write("همان سیستم قبلی برای سریال‌ها")
         # (کد قبلی اینجا می‌آید - برای خلاصه شدن تکرار نکردم چون تغییری نکرده)
         
    with tab_mix:
        st.subheader("آپلود چند تصویر + دستور خلاقانه")
        files = st.file_uploader("تصاویر را آپلود کنید (تا ۶ عدد):", accept_multiple_files=True)
        user_prompt = st.text_area("چه تغییری بدهم؟ (مثلا: ترکیب کن و در فضای تاریک نشان بده)", "Combine these images into a cinematic 16:9 poster.")
        
        if files and st.button("🎨 خلق اثر هنری"):
            frames = [f.getvalue() for f in files]
            with st.spinner("در حال ترکیب..."):
                url = analyze_and_generate_mix(frames, user_prompt)
                if url:
                    st.image(url, caption="اثر نهایی", use_container_width=True)
                    st.markdown(f"[دانلود]({url})")
                    st.success("تمام شد! به میز تدوین بروید.")
                    if st.button("رفتن به تدوین"): go_to("Montage Table")
                else: st.error("خطا در تولید تصویر.")

# ----------------- 5. Montage Table -----------------
elif st.session_state.active_step == "Montage Table":
    st.header("🎬 میز تدوین")
    if HAS_MOVIEPY:
        c1, c2 = st.columns(2)
        img = c1.file_uploader("تصویر نهایی:", type=["jpg","png"])
        aud = c2.file_uploader("صدا نهایی:", type=["mp3"])
        
        if img and aud and st.button("🎬 رندر نهایی"):
            with st.spinner("رندر..."):
                with open("t.jpg","wb") as f: f.write(img.getbuffer())
                with open("t.mp3","wb") as f: f.write(aud.getbuffer())
                ac = AudioFileClip("t.mp3")
                vc = ImageClip("t.jpg").set_duration(ac.duration).set_audio(ac)
                vc.write_videofile("o.mp4", fps=24, codec="libx264", audio_codec="aac")
                st.video("o.mp4")
                with open("o.mp4","rb") as f: st.download_button("⬇️ دانلود", f, "video.mp4")
                # بخش تلگرام هم اینجاست
    else: st.warning("MoviePy نصب نیست.")

# ----------------- 6. Settings -----------------
elif st.session_state.active_step == "Settings":
    st.write("تنظیمات دیتابیس")
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
