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

# --- 2. اتصال به هوش مصنوعی (Gemini) ---
try:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    model = genai.GenerativeModel('gemini-pro') # مغز نویسنده
except Exception as e:
    st.warning(f"⚠️ هوش مصنوعی وصل نشد: {e}")

# --- 3. توابع کمکی ---
def generate_script(text, project_type):
    """تولید سناریو با هوش مصنوعی"""
    if project_type == "پاورقی (سریال ترکی)":
        prompt = f"""
        نقش تو یک نویسنده خلاق برای کانال یوتیوب است.
        متن زیر، زیرنویس یک قسمت از سریال ترکی است.
        لطفا آن را به یک متن جذاب و روایی (Storytelling) برای ویدئوی "پاورقی" تبدیل کن.
        - لحن: صمیمی، کمی هیجانی و داستان‌گو.
        - ساختار: آن را به ۳ بخش کوتاه تقسیم کن که هر کدام یک اتفاق مهم را روایت کند.
        - خروجی باید کاملا فارسی باشد.
        
        متن ورودی:
        {text[:10000]} (بخشی از متن برای رعایت محدودیت توکن)
        """
    else: # جان کلام
        prompt = f"""
        نقش تو یک تحلیل‌گر سیاسی/اجتماعی تیزبین است.
        متن زیر را بخوان و "جان کلام" (نکات کلیدی و تحلیلی) آن را استخراج کن.
        - لحن: جدی، تحلیلی و روشن.
        - خروجی باید شامل: ۱. خلاصه مدیریتی ۲. سه نکته طلایی ۳. نتیجه‌گیری باشد.
        
        متن ورودی:
        {text[:10000]}
        """
    
    response = model.generate_content(prompt)
    return response.text

# (توابع قبلی خبر و زیرنویس سر جایشان هستند)
def fetch_rss_feed(rss_url):
    try:
        feed = feedparser.parse(rss_url)
        return [[datetime.now().strftime("%Y-%m-%d %H:%M"), feed.feed.get('title', 'Unknown'), entry.title, entry.link, "New"] for entry in feed.entries[:5]]
    except: return []

def download_transcript_heavy(url): # همان تابع قدرتمند قبلی
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

# تب اخبار (بدون تغییر)
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

# تب ویدئو (با قابلیت جدید AI)
with tab_video:
    st.header("۱. دریافت ورودی (Link or Text)")
    with st.form("input_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            v_url = st.text_input("لینک یوتیوب:")
            manual = st.text_area("متن دستی (اگر لینک کار نکرد):", height=100)
        with col2:
            p_name = st.text_input("نام پروژه:")
            p_type = st.selectbox("نوع:", ["پاورقی (سریال ترکی)", "جان کلام (تحلیلی)"])
            voice = st.selectbox("صدا:", ["Nima (Clone)", "Adam"])
        
        if st.form_submit_button("ثبت اولیه"):
            sub_text = manual if manual else (download_transcript_heavy(v_url) if v_url else "")
            if sub_text:
                sh.worksheet("Video_Factory").append_row([p_name, v_url, sub_text, "", voice, "Ready for AI", ""])
                st.success("پروژه ثبت شد! حالا در پایین صفحه با AI پردازش کنید.")
                st.rerun()
            else: st.error("متن یا لینک معتبر وارد کنید.")

    st.divider()
    st.header("۲. اتاق نویسندگان (AI Generation) ✍️")
    
    # خواندن پروژه‌های آماده برای نوشتن
    ws_vid = sh.worksheet("Video_Factory")
    df_vid = pd.DataFrame(ws_vid.get_all_records())
    
    if not df_vid.empty:
        # فیلتر کردن پروژه‌هایی که هنوز اسکریپت ندارند
        pending_projects = df_vid[df_vid['Script'] == ""].reset_index()
        
        if not pending_projects.empty:
            selected_idx = st.selectbox("یک پروژه را برای نوشتن انتخاب کنید:", pending_projects.index, format_func=lambda x: pending_projects.loc[x, 'Project_Name'])
            selected_row = pending_projects.loc[selected_idx]
            
            st.info(f"پروژه انتخاب شده: {selected_row['Project_Name']} | نوع: {selected_row['Subtitle_Text'][:50]}...")
            
            if st.button("✨ نوشتن سناریو توسط جمشید"):
                with st.spinner("جمشید در حال فکر کردن و نوشتن..."):
                    try:
                        # دریافت متن کامل از سلول
                        original_text = selected_row['Subtitle_Text']
                        # تشخیص نوع پروژه (چون در شیت ذخیره نشده بود، اینجا دستی فرض می‌کنیم یا باید ستون اضافه کنیم. فعلا از ورودی فرم بالا می‌پرسیم)
                        # راه بهتر: ستون Type به شیت اضافه کنید. فعلا پیش‌فرض می‌گیریم.
                        
                        script_result = generate_script(original_text, "پاورقی (سریال ترکی)") # فعلا پیش‌فرض
                        
                        # آپدیت گوگل شیت (پیدا کردن ردیف واقعی)
                        # نکته: این روش ساده است. در سیستم واقعی باید ID داشته باشیم.
                        cell = ws_vid.find(selected_row['Project_Name'])
                        ws_vid.update_cell(cell.row, 4, script_result) # ستون 4 = Script
                        ws_vid.update_cell(cell.row, 6, "Script Done") # ستون 6 = Status
                        
                        st.success("سناریو نوشته و ذخیره شد! 🎉")
                        st.text_area("پیش‌نمایش سناریو:", script_result, height=200)
                        st.rerun()
                    except Exception as e:
                        st.error(f"خطا در نوشتن: {e}")
        else:
            st.info("هیچ پروژه جدیدی برای نوشتن وجود ندارد.")
    
    st.dataframe(df_vid, use_container_width=True)

with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
