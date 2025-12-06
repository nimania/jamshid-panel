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
from bs4 import BeautifulSoup

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
        if project_type == "پاورقی (سریال ترکی)":
            system_msg = "تو نویسنده خلاق یوتیوب هستی. زیرنویس را به سناریوی جذاب فارسی تبدیل کن (۳ بخش متوالی). لحن: صمیمی و داستان‌گو."
        elif project_type == "جان کلام (تحلیلی)":
            system_msg = "تو تحلیلگر هستی. یک ری‌کپ حرفه‌ای، دقیق و موشکافانه از گفته‌های این متن تهیه کن."
        else: 
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
        content_list = [{"type": "text", "text": f"Create a DALL-E 3 prompt based on these images. Instruction: {user_instruction}. Style: Pastel Painting, Cinematic, 16:9 Aspect Ratio. No Text."}]
        for img in images_bytes[:2]: 
            b64 = base64.b64encode(img).decode('utf-8')
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        vision_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are an art director."}, {"role": "user", "content": content_list}], 
            max_tokens=200
        )
        mix_prompt = vision_response.choices[0].message.content
        image_response = client.images.generate(model="dall-e-3", prompt=f"{mix_prompt}. Aspect Ratio 16:9.", size="1792x1024", n=1)
        return image_response.data[0].url
    except Exception as e: return None

def generate_audio_flexible(text, voice_id, model_choice):
    """تولید صدا با انتخاب مدل دقیق"""
    try:
        safe_text = text[:5000] # مدل‌های جدید محدودیت کمتری دارند
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": st.secrets["elevenlabs"]["api_key"], "Content-Type": "application/json"}
        
        data = {
            "text": safe_text, 
            "model_id": model_choice, # استفاده از مدل انتخابی کاربر
            "voice_settings": {
                "stability": 0.50,
                "similarity_boost": 0.80,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        r = requests.post(url, json=data, headers=headers)
        if r.status_code == 200: return r.content, None
        else: return None, r.text
    except Exception as e: return None, str(e)

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

# --- توابع کمکی ---
def fetch_website_meta(url):
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.string if soup.title else url
        return [[datetime.now().strftime("%Y-%m-%d %H:%M"), "Website", title, url, "New"]]
    except: return []

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
steps = ["News Room", "Scenario Studio", "Sound Factory", "Art Gallery", "Montage Table", "Settings"]
selected_step = st.sidebar.radio("مراحل تولید:", steps, index=steps.index(st.session_state.active_step))
if selected_step != st.session_state.active_step:
    st.session_state.active_step = selected_step
    st.rerun()

# ----------------- 1. News Room -----------------
if st.session_state.active_step == "News Room":
    st.header("📰 اتاق خبر")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("۱. دریافت خودکار")
        if st.button("🔄 فراخوانی منابع"):
            ws_conf = sh.worksheet("Config")
            temp_list = []
            for item in ws_conf.get_all_records():
                if item['Type'] == 'RSS' and item['Value']: temp_list.extend(fetch_rss_feed(item['Value']))
                elif item['Type'] == 'Website' and item['Value']: temp_list.extend(fetch_website_meta(item['Value']))
            st.session_state.temp_news = temp_list
            if temp_list: st.success(f"{len(temp_list)} آیتم پیدا شد.")
            else: st.warning("چیزی پیدا نشد.")

    with col2:
        st.subheader("۲. ورودی دستی")
        with st.form("manual_news"):
            m_source = st.selectbox("منبع:", ["Twitter (X)", "Telegram", "Instagram", "Other"])
            m_title = st.text_input("تیتر/خلاصه خبر:")
            m_link = st.text_input("لینک پست:")
            if st.form_submit_button("افزودن"):
                st.session_state.temp_news.append([datetime.now().strftime("%Y-%m-%d %H:%M"), m_source, m_title, m_link, "New"])
                st.rerun()

    st.divider()
    st.subheader("۳. تایید نهایی")
    if st.session_state.temp_news:
        df_temp = pd.DataFrame(st.session_state.temp_news, columns=["Date", "Source", "Title", "Link", "Status"])
        edited_df = st.data_editor(df_temp, num_rows="dynamic", use_container_width=True)
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("💾 ذخیره در دیتابیس"):
            final_data = edited_df.values.tolist()
            if final_data:
                sh.worksheet("News_Feed").append_rows([r + [""] for r in final_data])
                st.session_state.temp_news = []
                st.success("ذخیره شد!"); time.sleep(1); go_to("Scenario Studio")
        if col_s2.button("❌ پاک کردن لیست"): st.session_state.temp_news = []; st.rerun()
    else:
        st.info("لیست موقت خالی است.")
        with st.expander("آرشیو دیتابیس"):
            try: st.dataframe(pd.DataFrame(sh.worksheet("News_Feed").get_all_records()))
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
            style = st.radio("مود نویسنده:", ["پاورقی (سریال ترکی)", "جان کلام (تحلیلی)", "✨ پرامت آزاد (Custom)"], horizontal=True)
            custom_prompt = ""
            if style == "✨ پرامت آزاد (Custom)": custom_prompt = st.text_area("دستور اختصاصی:", "بازنویسی خلاقانه...")
            
            if st.button("✨ نوشتن سناریو"):
                with st.spinner("نویسنده در حال کار..."):
                    res = generate_script_gpt(row['Subtitle_Text'], style, custom_prompt)
                    cell = ws_vid.find(row['Project_Name'])
                    ws_vid.update_cell(cell.row, 4, res)
                    st.toast("آماده شد!", icon="🎙️"); time.sleep(1); go_to("Sound Factory")
    except: pass

# ----------------- 3. Sound Factory -----------------
elif st.session_state.active_step == "Sound Factory":
    st.header("🎙️ کارخانه صدا")
    st.info("مجهز به موتورهای نسل جدید ElevenLabs")
    
    # >>> منوی انتخاب موتور صدا (با گزینه V3) <<<
    model_options = {
        "Eleven V3 / Turbo v2.5 (جدید و سریع)": "eleven_turbo_v2_5",
        "Multilingual v2 (بهترین کیفیت داستانی)": "eleven_multilingual_v2",
        "Flash v2.5 (فوق سریع)": "eleven_flash_v2_5"
    }
    
    selected_model_label = st.selectbox("انتخاب موتور هوش مصنوعی صدا:", list(model_options.keys()))
    selected_model_id = model_options[selected_model_label]
    
    subtab_proj, subtab_free = st.tabs(["📂 بر اساس پروژه", "✍️ متن آزاد"])
    
    # 1. حالت پروژه
    with subtab_proj:
        try:
            ws_vid = sh.worksheet("Video_Factory")
            df = pd.DataFrame(ws_vid.get_all_records())
            if not df.empty:
                ready = df[df['Script'] != ""].reset_index()
                if not ready.empty:
                    idx = st.selectbox("پروژه دیتابیس:", ready.index, index=len(ready)-1, format_func=lambda x: ready.loc[x, 'Project_Name'])
                    row = ready.loc[idx]
                    txt = st.text_area("ویرایش سناریو:", row['Script'], height=200)
                    
                    if st.button("🎙️ تولید صدا (پروژه)"):
                        with st.spinner(f"ضبط با موتور {selected_model_id}..."):
                            if txt != row['Script']:
                                cell = ws_vid.find(row['Project_Name'])
                                ws_vid.update_cell(cell.row, 4, txt)
                            
                            aud, err = generate_audio_flexible(txt, row['Voice_ID'], selected_model_id)
                            if aud:
                                st.audio(aud, format='audio/mp3')
                                st.success(f"✅ تولید شد! (مدل: {selected_model_id})")
                                time.sleep(2); go_to("Art Gallery")
                            else: st.error(err)
        except: pass

    # 2. حالت متن آزاد
    with subtab_free:
        col_f1, col_f2 = st.columns([3, 1])
        with col_f1:
            free_text = st.text_area("متن دلخواه:", height=150, placeholder="سلام...")
        with col_f2:
            voice_dict_free = get_elevenlabs_voices()
            idx_vip = list(voice_dict_free.keys()).index("Nima (VIP)") if "Nima (VIP)" in voice_dict_free else 0
            selected_voice = st.selectbox("انتخاب صدا:", list(voice_dict_free.keys()), index=idx_vip)
        
        if st.button("🎙️ تولید صدای آزاد"):
            if not free_text: st.error("متن خالی است.")
            else:
                with st.spinner(f"تولید با موتور {selected_model_id}..."):
                    voice_id_free = voice_dict_free.get(selected_voice)
                    aud_free, err_free = generate_audio_flexible(free_text, voice_id_free, selected_model_id)
                    if aud_free:
                        st.audio(aud_free, format='audio/mp3')
                        st.success(f"✅ صدا آماده است! (مدل: {selected_model_id})")
                    else: st.error(err_free)

# ----------------- 4. Art Gallery -----------------
elif st.session_state.active_step == "Art Gallery":
    st.header("🎨 گالری تصاویر")
    tab_auto, tab_mix = st.tabs(["📸 شکار خودکار", "📂 ترکیب دستی"])
    with tab_auto:
         st.write("سیستم خودکار (نیازمند VPN)") 
         # کد قبلی...
         
    with tab_mix:
        st.subheader("آپلود چند تصویر + دستور خلاقانه")
        files = st.file_uploader("آپلود (تا ۶ عدد):", accept_multiple_files=True)
        user_prompt = st.text_area("توصیف:", "Combine into cinematic 16:9 poster.")
        if files and st.button("🎨 خلق اثر"):
            frames = [f.getvalue() for f in files]
            with st.spinner("در حال نقاشی..."):
                url = analyze_and_generate_mix(frames, user_prompt)
                if url: 
                    st.image(url)
                    st.markdown(f"[⬇️ دانلود]({url})")
                    if st.button("رفتن به تدوین"): go_to("Montage Table")
                else: st.error("خطا.")

# ----------------- 5. Montage Table -----------------
elif st.session_state.active_step == "Montage Table":
    st.header("🎬 میز تدوین")
    if HAS_MOVIEPY:
        c1, c2 = st.columns(2)
        img = c1.file_uploader("تصویر:", type=["jpg","png"])
        aud = c2.file_uploader("صدا:", type=["mp3"])
        if img and aud and st.button("🎬 رندر"):
            with st.spinner("رندر..."):
                with open("t.jpg","wb") as f: f.write(img.getbuffer())
                with open("t.mp3","wb") as f: f.write(aud.getbuffer())
                ac = AudioFileClip("t.mp3")
                vc = ImageClip("t.jpg").set_duration(ac.duration).set_audio(ac)
                vc.write_videofile("o.mp4", fps=24, codec="libx264", audio_codec="aac")
                st.video("o.mp4")
                with open("o.mp4","rb") as f: st.download_button("⬇️ دانلود", f, "final.mp4")
    else: st.warning("MoviePy نصب نیست.")

# ----------------- 6. Settings -----------------
elif st.session_state.active_step == "Settings":
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
