import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import feedparser
import yt_dlp
import re
from datetime import datetime
import google.generativeai as genai

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

# --- 2. اتصال به Gemini 1.5 Pro ---
try:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    # استفاده از قدرتمندترین مدل موجود
    model = genai.GenerativeModel('gemini-1.5-pro') 
except Exception as e:
    st.warning(f"⚠️ هوش مصنوعی وصل نشد: {e}")

# --- 3. توابع کمکی ---
def generate_script(text, project_type):
    if not text: return "متنی برای پردازش وجود ندارد."
    
    if project_type == "پاورقی (سریال ترکی)":
        prompt = f"""
        نقش تو یک نویسنده خلاق و داستان‌گو برای کانال یوتیوب است.
        ورودی زیر، متن خام یا زیرنویس یک سریال است.
        آن را به یک سناریوی ویدئویی جذاب "پاورقی" تبدیل کن.
        
        دستورالعمل‌ها:
        1. لحن: صمیمی، ایرانی‌پسند، کمی طنزآمیز و کنجکاو کننده.
        2. ساختار: مقدمه (قلاب)، بدنه داستان (3 اتفاق مهم)، و پایان‌بندی (نتیجه‌گیری).
        3. زبان: فارسی روان و محاوره.
        
        متن ورودی:
        {text[:25000]} 
        """
    else: 
        prompt = f"""
        نقش تو یک تحلیل‌گر استراتژیک است.
        متن زیر را بخوان و "جان کلام" را استخراج کن.
        خروجی باید شامل: خلاصه مدیریتی، ۳ نکته کلیدی، و تحلیل اثرات آینده باشد.
        
        متن ورودی:
        {text[:25000]}
        """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطا در تولید: {e}"

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
            if 'subtitles' in info and info['subtitles']: return "زیرنویس یافت شد."
            if 'automatic_captions' in info: return "زیرنویس اتوماتیک یافت شد."
        return None
    except: return None

# --- 4. رابط کاربری ---
st.title("👑 اتاق فرمان جمشید (مجهز به Gemini 1.5 Pro)")
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
            voice = st.selectbox("صدا:", ["Nima (Clone)", "Adam"])
        
        if st.form_submit_button("ثبت"):
            sub_text = manual if manual else (download_transcript_heavy(v_url) if v_url else "")
            if sub_text:
                sh.worksheet("Video_Factory").append_row([p_name, v_url, sub_text, "", voice, "Ready for AI", ""])
                st.success("ثبت شد!")
                st.rerun()
            else: st.error("متن یا لینک معتبر وارد کنید.")

    st.divider()
    st.header("۲. اتاق نویسندگان (Gemini Pro) 🧠")
    
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df_vid = pd.DataFrame(ws_vid.get_all_records())
        
        if not df_vid.empty:
            pending = df_vid[df_vid['Script'] == ""].reset_index()
            if not pending.empty:
                sel_idx = st.selectbox("انتخاب پروژه:", pending.index, format_func=lambda x: f"{pending.loc[x, 'Project_Name']}")
                sel_row = pending.loc[sel_idx]
                
                if st.button("✨ نوشتن سناریو"):
                    with st.spinner("جمشید (1.5 Pro) در حال نوشتن..."):
                        res = generate_script(sel_row['Subtitle_Text'], "پاورقی (سریال ترکی)")
                        if "خطا" not in res:
                            cell = ws_vid.find(sel_row['Project_Name'])
                            ws_vid.update_cell(cell.row, 4, res)
                            ws_vid.update_cell(cell.row, 6, "Script Done")
                            st.success("تمام شد!")
                            st.text_area("خروجی:", res, height=300)
                        else: st.error(res)
            else: st.info("همه پروژه‌ها انجام شده‌اند.")
        st.dataframe(df_vid, use_container_width=True)
    except: pass

with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
