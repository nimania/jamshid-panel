import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import feedparser
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import re
from datetime import datetime

st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

# --- اتصال به دیتابیس ---
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
        st.error(f"❌ خطای اتصال: {e}")
        st.stop()

sh = connect_to_db()

# --- توابع کمکی ---
def fetch_rss_feed(rss_url):
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
    if not url: return None
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})']
    for pattern in patterns:
        match = re.search(pattern, url)
        if match: return match.group(1)
    return None

def download_transcript(video_id):
    """دانلود هوشمند زیرنویس (حتی اتوماتیک)"""
    try:
        # 1. لیست کردن تمام زیرنویس‌های موجود
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # 2. تلاش برای یافتن زیرنویس‌های ترجیحی
        try:
            transcript = transcript_list.find_transcript(['fa', 'en', 'tr'])
        except:
            # 3. اگر نبود، اولین زیرنویس موجود (معمولا اتوماتیک) را بردار
            transcript = next(iter(transcript_list))
            
        # 4. دریافت و فرمت‌دهی متن
        return TextFormatter().format_transcript(transcript.fetch())
        
    except Exception as e:
        # اگر هیچ جوره زیرنویس نداشت
        return None

# --- رابط کاربری ---
st.title("👑 اتاق فرمان جمشید")

tab_news, tab_video, tab_config = st.tabs(["📰 اتاق خبر", "🎬 کارخانه ویدئو", "⚙️ تنظیمات"])

# تب ۱: اخبار
with tab_news:
    col1, col2 = st.columns([4, 1])
    with col1: st.subheader("اخبار روز")
    with col2:
        if st.button("🔄 دریافت اخبار"):
            with st.spinner('در حال رصد...'):
                try:
                    ws_config = sh.worksheet("Config")
                    new_news = []
                    found = False
                    for item in ws_config.get_all_records():
                        if item['Type'] == 'RSS' and item['Value']:
                            found = True
                            new_news.extend(fetch_rss_feed(item['Value']))
                    
                    if new_news:
                        sh.worksheet("News_Feed").append_rows([n + [""] for n in new_news])
                        st.success(f"{len(new_news)} خبر جدید!")
                        st.rerun()
                    elif not found: st.warning("RSS تنظیم نشده.")
                    else: st.info("خبر جدیدی نیست.")
                except Exception as e: st.error(f"خطا: {e}")

    try:
        st.dataframe(pd.DataFrame(sh.worksheet("News_Feed").get_all_records()), use_container_width=True)
    except: st.warning("تب News_Feed یافت نشد.")

# تب ۲: ویدئو
with tab_video:
    st.header("تولید محتوا")
    with st.form("video_form"):
        col_input, col_settings = st.columns([2, 1])
        with col_input:
            video_url = st.text_input("🔗 لینک یوتیوب:")
            manual_text = st.text_area("📝 متن دستی (اگر اتوماتیک نشد):", height=100)
        with col_settings:
            project_name = st.text_input("نام پروژه:")
            voice = st.selectbox("🎙️ گوینده:", ["Nima (Clone)", "Adam", "Sarah"])
        if st.form_submit_button("🚀 دریافت و ثبت"):
            status = st.status("در حال کار...", expanded=True)
            try:
                final_sub = ""
                if video_url:
                    vid_id = get_video_id(video_url)
                    if vid_id:
                        status.write("⏳ جستجوی زیرنویس (حتی اتوماتیک)...")
                        final_sub = download_transcript(vid_id)
                        if final_sub: status.write("✅ زیرنویس پیدا شد!")
                
                if not final_sub and manual_text:
                    final_sub = manual_text
                    status.write("✅ استفاده از متن دستی.")
                
                if final_sub:
                    sh.worksheet("Video_Factory").append_row([
                        project_name or "New", video_url, final_sub[:40000], "", voice, "Ready", ""
                    ])
                    status.update(label="ثبت شد! 🎉", state="complete")
                    st.rerun()
                else:
                    status.update(label="ناموفق", state="error")
                    st.error("این ویدئو هیچ زیرنویسی (حتی اتوماتیک) ندارد. لطفاً متن را دستی وارد کنید.")
            except Exception as e: st.error(f"خطا: {e}")
            
    try:
        st.dataframe(pd.DataFrame(sh.worksheet("Video_Factory").get_all_records()), use_container_width=True)
    except: pass

# تب ۳: تنظیمات
with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
