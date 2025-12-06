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

# --- توابع کمکی (ابزارها) ---
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
    video_id = None
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
    """دانلود زیرنویس فارسی یا انگلیسی"""
    try:
        # اول تلاش برای فارسی، بعد انگلیسی، بعد ترکی
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
            with st.spinner('در حال رصد خبرگزاری‌ها...'):
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
