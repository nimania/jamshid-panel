import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import feedparser
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import re
from datetime import datetime

# --- تنظیمات صفحه ---
st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

# --- اتصال به دیتابیس ---
@st.cache_resource
def connect_to_db():
    try:
        # کپی کردن دیکشنری برای جلوگیری از تغییر ناخواسته
        info = dict(st.secrets["gcp_service_account"]).copy()
        
        # اصلاح کلید خصوصی (New line fix)
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
            
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open("Command_Center")
    except Exception as e:
        st.error(f"❌ خطای اتصال: {e}")
        st.stop()

sh = connect_to_db()

# --- توابع کمکی ---
def fetch_rss_feed(rss_url):
    """خبرخوان RSS"""
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:5]:
            news_items.append([
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                feed.feed.get('title', 'Unknown'),
                entry.title,
                entry.link,
                "New"
            ])
        return news_items
    except:
        return []

def get_video_id(url):
    """استخراج ID ویدئو از لینک یوتیوب"""
    if not url: return None
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def download_transcript(video_id):
    """دانلود زیرنویس"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['fa', 'en', 'tr'])
        formatter = TextFormatter()
        return formatter.format_transcript(transcript)
    except Exception as e:
        return None

# --- رابط کاربری (UI) ---
st.title("👑 اتاق فرمان جمشید")

tab_news, tab_video, tab_future, tab_config = st.tabs(["📰 اتاق خبر", "🎬 کارخانه ویدئو", "🔮 آینده‌پژوهی", "⚙️ تنظیمات"])

# 1️⃣ تب اتاق خبر
with tab_news:
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("تازه ترین اخبار")
    with col2:
        if st.button("🔄 دریافت اخبار جدید"):
            with st.spinner('در حال رصد...'):
                try:
                    ws_config = sh.worksheet("Config")
                    configs = ws_config.get_all_records()
                    new_news = []
                    found_rss = False
                    for item in configs:
                        if item['Type'] == 'RSS' and item['Value']:
                            found_rss = True
                            new_news.extend(fetch_rss_feed(item['Value']))
                    
                    if new_news:
                        ws_news = sh.worksheet("News_Feed")
                        for news in new_news:
                            ws_news.append_row(news + [""])
                        st.success(f"{len(new_news)} خبر جدید!")
                        st.rerun()
                    elif not found_rss:
                        st.warning("RSS تعریف نشده است.")
                    else:
                        st.info("خبر جدیدی نیست.")
                except Exception as e:
                    st.error(f"خطا: {e}")

    # نمایش جدول اخبار (بخش اصلاح شده که خطا داشت)
    try:
        ws_news = sh.worksheet("News_Feed")
        st.dataframe(pd.DataFrame(ws_news.get_all_records()), use_container_width=True)
    except:
        st.warning("تب News_Feed در گوگل شیت یافت نشد.")

# 2️⃣ تب کارخانه ویدئو
with tab_video:
    st.header("تولید محتوای ویدئویی")
    
    with st.form("video_form"):
        col_input, col_settings = st.columns([2, 1])
        with col_input:
            video_url = st.text_input("🔗 لینک یوتیوب:")
            manual_text = st.text_area("📝 متن دستی (جایگزین):", height=100)
        
        with col_settings:
            project_name = st.text_input("نام پروژه:")
            voice_model = st.selectbox("🎙️ گوینده:", ["Nima (Clone)", "Adam", "Sarah"])
        
        submit_btn = st.form_submit_button("🚀 دریافت زیرنویس و ثبت")
    
    if submit_btn:
        status = st.status("در حال پردازش...", expanded=True)
        try:
            final_subtitle = ""
            if video_url:
                vid_id = get_video_id(video_url)
                if vid_id:
                    status.write("⏳ دانلود زیرنویس...")
                    sub = download_transcript(vid_id)
                    if sub:
                        final_subtitle = sub
                        status.write("✅ زیرنویس دانلود شد.")
            
            if not final_subtitle and manual_text:
                final_subtitle = manual_text
                status.write("✅ متن دستی اعمال شد.")
            
            if final_subtitle:
                ws_video = sh.worksheet("Video_Factory")
                row_data = [
                    project_name if project_name else "New Project",
                    video_url,
                    final_subtitle[:40000], 
                    "", 
                    voice_model,
                    "Ready", 
                    ""
                ]
                ws_video.append_row(row_data)
                status.update(label="ثبت شد! 🎉", state="complete")
                st.rerun()
            else:
                status.update(label="ناموفق", state="error")
                st.error("زیرنویس پیدا نشد. لطفا متن دستی وارد کنید.")
        except Exception as e:
            st.error(f"خطا: {e}")

    st.divider()
    try:
        ws_video = sh.worksheet("Video_Factory")
        st.dataframe(pd.DataFrame(ws_video.get_all_records()), use_container_width=True)
    except:
        pass

# 3️⃣ تب‌های دیگر
with tab_future:
    st.write("به زودی...")
with tab_config:
    try:
        st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except:
        st.write("تب Config خالی است.")
