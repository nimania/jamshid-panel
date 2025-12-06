import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. تنظیمات اولیه صفحه ---
st.set_page_config(
    page_title="Jamshid Command Center",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. اتصال به گوگل شیت (مغز سیستم) ---
@st.cache_resource
def get_db():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # دریافت اطلاعات محرمانه از Secrets استریم‌لیت
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Command_Center")

try:
    sh = get_db()
    st.toast("جمشید آنلاین است و به حافظه متصل شد! 🧠", icon="✅")
except Exception as e:
    st.error(f"خطا در اتصال به دیتابیس: {e}")
    st.info("نکته: مطمئن شوید فایل secrets.toml را در تنظیمات استریم‌لیت درست وارد کرده‌اید.")
    st.stop()

# --- 3. نوار کناری (Sidebar) ---
with st.sidebar:
    st.title("👑 جمشید")
    st.caption("دستیار هوشمند پندار مدیا")
    st.divider()
    
    # دکمه‌های عملیاتی سریع
    if st.button("🔄 بررسی منابع خبری (RSS)", use_container_width=True):
        st.toast("در حال چک کردن منابع خبری...", icon="📰")
    
    if st.button("📺 رصد یوتیوب (سریال‌ها)", use_container_width=True):
        st.toast("در حال جستجوی قسمت‌های جدید...", icon="🕵️")
        
    st.divider()
    st.markdown("### وضعیت سیستم")
    st.success("APIها: متصل")
    st.success("ElevenLabs: آماده")

# --- 4. تب‌های اصلی ---
tab_news, tab_video, tab_future, tab_config = st.tabs([
    "📰 اتاق خبر (News Room)", 
    "🎬 کارخانه ویدئو (Studio)", 
    "🔮 آینده‌پژوهی (Futures)", 
    "⚙️ تنظیمات (Config)"
])

# --- تب ۱: اتاق خبر ---
with tab_news:
    st.header("دیده‌بانی و مدیریت اخبار")
    try:
        ws_news = sh.worksheet("News_Feed")
        data_news = ws_news.get_all_records()
        df_news = pd.DataFrame(data_news)
        
        if not df_news.empty:
            st.dataframe(df_news, use_container_width=True)
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                selected_news = st.selectbox("انتخاب خبر برای پردازش:", df_news['Title']) if 'Title' in df_news.columns else None
            with col2:
                st.radio("اقدام:", ["ارسال به پندارمدیا", "ارسال به آینده‌پژوهی", "حذف"], horizontal=True)
            if st.button("اجرای فرمان ⚡"):
                st.write(f"خبر '{selected_news}' پردازش شد.")
        else:
            st.info("صف اخبار خالی است.")
    except Exception as e:
        st.warning(f"مشکل در خواندن تب News_Feed: {e}")

# --- تب ۲: کارخانه ویدئو ---
with tab_video:
    st.header("تولید محتوای ویدئویی")
    col_input, col_settings = st.columns([2, 1])
    
    with col_input:
        video_url = st.text_input("🔗 لینک ویدیو یوتیوب:", placeholder="https://youtube.com/...")
        with st.expander("📝 تنظیمات دستی زیرنویس"):
            manual_sub_option = st.checkbox("استفاده از زیرنویس دستی")
            if manual_sub_option:
                st.text_area("متن زیرنویس:", height=150)

    with col_settings:
        st.selectbox("نوع پروژه:", ["پاورقی (سریال ترکی)", "جان کلام (تحلیلی)"])
        voice_model = st.selectbox("🎙️ انتخاب گوینده:", ["Nima (Clone)", "Adam", "Sarah"])
        
    if st.button("🚀 شروع پردازش", type="primary"):
        if not video_url:
            st.error("لطفا لینک ویدئو را وارد کنید.")
        else:
            st.success("درخواست به جمشید ارسال شد! (شبیه‌سازی)")

# --- تب ۳ و ۴ ---
with tab_future:
    st.header("آزمایشگاه آینده‌پژوهی")
    try:
        ws_futures = sh.worksheet("Futures_Lab")
        st.dataframe(pd.DataFrame(ws_futures.get_all_records()))
    except:
        st.write("تب Futures_Lab خالی است.")

with tab_config:
    st.header("مدیریت منابع")
    try:
        ws_config = sh.worksheet("Config")
        st.data_editor(pd.DataFrame(ws_config.get_all_records()), num_rows="dynamic")
    except:
        st.write("تب Config یافت نشد.")
