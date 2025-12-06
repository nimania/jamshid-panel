import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import feedparser
import yt_dlp
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

def download_transcript_heavy(url):
    """دانلود زیرنویس با موتور قدرتمند yt-dlp"""
    try:
        # تنظیمات برای دانلود نکردن ویدئو و فقط گرفتن زیرنویس در حافظه
        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,      # زیرنویس اتوماتیک را هم بگیر
            'subtitleslangs': ['fa', 'en', 'tr'], # زبان‌های اولویت دار
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # استخراج متن زیرنویس از دیتای خام (کمی پیچیده است چون فایل نمی‌سازیم)
            # نکته: yt-dlp متن را مستقیم نمی‌دهد مگر اینکه دانلود کنیم.
            # اما اینجا چک می‌کنیم آیا اصلا زیرنویس دارد یا نه.
            
            if 'subtitles' in info and info['subtitles']:
                # اولویت با دستی
                for lang in ['fa', 'en', 'tr']:
                    if lang in info['subtitles']:
                        return f"زیرنویس {lang} یافت شد (لینک دانلود در لاگ‌ها)" 
            
            if 'automatic_captions' in info and info['automatic_captions']:
                # اولویت دوم با اتوماتیک
                for lang in ['fa', 'en', 'tr']:
                    if lang in info['automatic_captions']:
                         # اینجا چون استریم‌لیت اجازه دانلود فایل موقت ندارد، 
                         # ما فقط تایید می‌کنیم که هست.
                         # برای متن کامل، فعلا روش دستی امن‌تر است.
                         return "زیرنویس اتوماتیک پیدا شد. (برای دریافت متن کامل روی سرور ابری محدودیت داریم)"

        return None
    except Exception as e:
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
    except: pass

# تب ۲: ویدئو
with tab_video:
    st.header("تولید محتوا")
    st.info("💡 نکته: اگر دریافت اتوماتیک به خاطر تحریم‌های سرور کار نکرد، متن را دستی وارد کنید.")
    
    with st.form("video_form"):
        col_input, col_settings = st.columns([2, 1])
        with col_input:
            video_url = st.text_input("🔗 لینک یوتیوب:")
            manual_text = st.text_area("📝 متن دستی (جایگزین):", height=150, help="متن را از Downsub کپی و اینجا پیست کنید.")
        with col_settings:
            project_name = st.text_input("نام پروژه:")
            voice = st.selectbox("🎙️ گوینده:", ["Nima (Clone)", "Adam", "Sarah"])
        
        if st.form_submit_button("🚀 ثبت پروژه"):
            status = st.status("در حال بررسی...", expanded=True)
            try:
                final_sub = ""
                
                # اولویت ۱: متن دستی (چون همیشه دقیق‌تر است)
                if manual_text:
                    final_sub = manual_text
                    status.write("✅ متن دستی دریافت شد.")
                
                # اولویت ۲: تلاش اتوماتیک (اگر دستی نبود)
                elif video_url:
                    # اینجا فعلاً فقط پیام می‌گذاریم چون دانلود فایل در کلاد دردسر دارد
                    # اما اگر بخواهید بعداً آن را فعال می‌کنیم.
                    status.warning("⚠️ متن دستی وارد نشده. تلاش برای دریافت اتوماتیک ممکن است روی سرور ابری مسدود شود.")
                
                if final_sub:
                    sh.worksheet("Video_Factory").append_row([
                        project_name or "New", video_url, final_sub[:40000], "", voice, "Ready", ""
                    ])
                    status.update(label="ثبت شد! 🎉", state="complete")
                    st.rerun()
                else:
                    status.update(label="توقف", state="error")
                    st.error("متنی پیدا نشد! لطفاً برای اطمینان متن را از Downsub کپی و در کادر دستی پیست کنید.")
            except Exception as e: st.error(f"خطا: {e}")
            
    try:
        st.dataframe(pd.DataFrame(sh.worksheet("Video_Factory").get_all_records()), use_container_width=True)
    except: pass

# تب ۳: تنظیمات
with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
