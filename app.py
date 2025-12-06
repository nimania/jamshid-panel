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

# --- 2. اتصال به هوش مصنوعی (حالت امن) ---
try:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    # استفاده از مدل استاندارد که همه جا کار می‌کند
    model = genai.GenerativeModel('gemini-pro') 
except Exception as e:
    st.warning(f"⚠️ هوش مصنوعی وصل نشد: {e}")

# --- 3. توابع کمکی ---
def generate_script(text, project_type):
    if not text: return "متنی برای پردازش وجود ندارد."
    
    # محدود کردن متن برای جلوگیری از خطای طولانی بودن (Token Limit)
    safe_text = text[:12000] 
    
    if project_type == "پاورقی (سریال ترکی)":
        prompt = f"""
        به عنوان یک نویسنده یوتیوب، متن زیر (بخشی از سریال) را به یک سناریوی جذاب "پاورقی" تبدیل کن.
        لحن: صمیمی و داستان‌گو.
        ساختار: مقدمه جذاب، ۳ اتفاق اصلی، نتیجه‌گیری.
        
        متن:
        {safe_text} 
        """
    else: 
        prompt = f"""
        به عنوان تحلیلگر، "جان کلام" متن زیر را استخراج کن.
        خروجی: خلاصه، ۳ نکته کلیدی، تحلیل آینده.
        
        متن:
        {safe_text}
        """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"خطا در تولید محتوا: {e}\n(ممکن است متن خیلی طولانی باشد یا API Key محدودیت داشته باشد)"

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
            voice = st.selectbox("صدا:", ["Nima (Clone)", "Adam"])
        
        if st.form_submit_button("ثبت"):
            sub_text = manual if manual else (download_transcript_heavy(v_url) if v_url else "")
            if sub_text:
                sh.worksheet("Video_Factory").append_row([p_name, v_url, sub_text, "", voice, "Ready for AI", ""])
                st.success("ثبت شد!")
                st.rerun()
            else: st.error("متن یا لینک معتبر وارد کنید.")

    st.divider()
    st.header("۲. اتاق نویسندگان (AI) ✍️")
    
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df_vid = pd.DataFrame(ws_vid.get_all_records())
        
        if not df_vid.empty:
            # فقط پروژه‌هایی که هنوز انجام نشده‌اند را نشان بده
            # اگر ستون Script خالی بود
            pending = df_vid[df_vid['Script'] == ""].reset_index()
            
            if not pending.empty:
                sel_idx = st.selectbox("انتخاب پروژه:", pending.index, format_func=lambda x: f"{pending.loc[x, 'Project_Name']}")
                sel_row = pending.loc[sel_idx]
                
                if st.button("✨ نوشتن سناریو"):
                    with st.spinner("جمشید در حال نوشتن..."):
                        # استفاده از ستون متن زیرنویس
                        text_to_process = sel_row['Subtitle_Text']
                        res = generate_script(text_to_process, "پاورقی (سریال ترکی)")
                        
                        if "خطا" not in res:
                            cell = ws_vid.find(sel_row['Project_Name'])
                            ws_vid.update_cell(cell.row, 4, res) # ذخیره سناریو
                            ws_vid.update_cell(cell.row, 6, "Done") # تغییر وضعیت
                            st.success("تمام شد!")
                            st.text_area("خروجی:", res, height=300)
                            st.rerun()
                        else: st.error(res)
            else: st.info("پروژه جدیدی نیست.")
        st.dataframe(df_vid, use_container_width=True)
    except: pass

with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
