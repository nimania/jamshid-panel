import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import feedparser
from datetime import datetime
import json

# --- تنظیمات صفحه ---
st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

# --- اتصال به دیتابیس ---
@st.cache_resource
def connect_to_db():
    try:
        # دریافت اطلاعات از Secrets (روش جدید)
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

# --- توابع کمکی (مغز متفکر) ---
def fetch_rss_feed(rss_url):
    """اخبار را از RSS می‌خواند"""
    feed = feedparser.parse(rss_url)
    news_items = []
    for entry in feed.entries[:5]: # گرفتن ۵ خبر آخر
        news_items.append([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            feed.feed.get('title', 'Unknown'),
            entry.title,
            entry.link,
            "New"
        ])
    return news_items

# --- رابط کاربری (UI) ---
st.title("👑 اتاق فرمان جمشید")

tab_news, tab_video, tab_future, tab_config = st.tabs([
    "📰 اتاق خبر", 
    "🎬 کارخانه ویدئو", 
    "🔮 آینده‌پژوهی", 
    "⚙️ تنظیمات"
])

# 1️⃣ تب اتاق خبر
with tab_news:
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("تازه ترین اخبار")
    with col2:
        if st.button("🔄 دریافت اخبار جدید"):
            with st.spinner('در حال رصد خبرگزاری‌ها...'):
                try:
                    # خواندن آدرس RSS از تب Config
                    ws_config = sh.worksheet("Config")
                    configs = ws_config.get_all_records()
                    
                    found_rss = False
                    new_news = []
                    
                    for item in configs:
                        if item['Type'] == 'RSS' and item['Value']:
                            found_rss = True
                            st.toast(f"در حال خواندن: {item['Name']}")
                            new_news.extend(fetch_rss_feed(item['Value']))
                    
                    if new_news:
                        ws_news = sh.worksheet("News_Feed")
                        # اضافه کردن به شیت
                        for news in new_news:
                            ws_news.append_row(news + [""]) # ستون خلاصه خالی
                        st.success(f"{len(new_news)} خبر جدید اضافه شد!")
                        st.rerun()
                    elif not found_rss:
                        st.error("هیچ آدرس RSS در تب تنظیمات (Config) پیدا نشد!")
                    else:
                        st.info("خبر جدیدی نبود.")
                        
                except Exception as e:
                    st.error(f"خطا: {e}")

    # نمایش جدول اخبار
    try:
        ws_news = sh.worksheet("News_Feed")
        data = ws_news.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("هنوز خبری نیست. دکمه بالا را بزنید (به شرطی که در Config لینک RSS گذاشته باشید).")
    except:
        st.warning("تب News_Feed پیدا نشد.")

# 2️⃣ تب کارخانه ویدئو
with tab_video:
    st.header("تولید محتوای ویدئویی")
    col_input, col_settings = st.columns([2, 1])
    
    with col_input:
        video_url = st.text_input("🔗 لینک یوتیوب:", placeholder="https://youtube.com/...")
        with st.expander("📝 تنظیمات دستی زیرنویس (اگر اتوماتیک کار نکرد)"):
            manual_sub_option = st.checkbox("استفاده از زیرنویس دستی")
            manual_text = st.text_area("متن زیرنویس را اینجا پیست کنید:", height=150)

    with col_settings:
        project_type = st.selectbox("نوع پروژه:", ["پاورقی (سریال ترکی)", "جان کلام (تحلیلی)"])
        voice_model = st.selectbox("🎙️ انتخاب گوینده:", ["Nima (Clone)", "Adam", "Sarah"])
        
    if st.button("🚀 شروع پردازش"):
        st.toast("درخواست ثبت شد! (در مراحل بعدی هوش مصنوعی اضافه می‌شود)")

# 3️⃣ تب آینده‌پژوهی
with tab_future:
    st.write("بخش تحلیل آینده‌پژوهی (به زودی)")

# 4️⃣ تب تنظیمات
with tab_config:
    st.write("### مدیریت منابع (RSS و یوتیوب)")
    try:
        ws_config = sh.worksheet("Config")
        df_conf = pd.DataFrame(ws_config.get_all_records())
        st.dataframe(df_conf, use_container_width=True)
        st.caption("نکته: برای اضافه کردن RSS، مستقیم در گوگل شیت ردیف اضافه کنید: Type=RSS, Value=Link")
    except:
        st.write("دیتایی نیست.")
