import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials # کتابخانه جدید و بهتر

# --- 1. تنظیمات صفحه ---
st.set_page_config(
    page_title="Jamshid Command Center",
    page_icon="👑",
    layout="wide"
)

# --- 2. اتصال قدرتمند به گوگل شیت ---
@st.cache_resource
def get_db():
    # خواندن اطلاعات از Secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # >>> فوت کوزه‌گری: اصلاح فرمت کلید خصوصی <<<
    # این خط مشکل شما را حل می‌کند
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    # تعریف سطح دسترسی
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # ساخت اعتبارنامه با روش جدید گوگل
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    return client.open("Command_Center")

# تست اتصال
try:
    sh = get_db()
    st.toast("اتصال برقرار شد! جمشید آماده است 👑", icon="✅")
except Exception as e:
    st.error(f"مشکل در اتصال: {e}")
    st.stop()

# --- 3. بدنه اصلی برنامه ---
st.title("👑 اتاق فرمان جمشید")

tab_news, tab_video, tab_future, tab_config = st.tabs([
    "📰 اتاق خبر", "🎬 کارخانه ویدئو", "🔮 آینده‌پژوهی", "⚙️ تنظیمات"
])

# --- تب ۱: اتاق خبر ---
with tab_news:
    st.header("مدیریت اخبار")
    try:
        ws = sh.worksheet("News_Feed")
        df = pd.DataFrame(ws.get_all_records())
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("هنوز خبری نیست.")
    except:
        st.warning("تب News_Feed یافت نشد.")

# --- تب ۲: کارخانه ویدئو ---
with tab_video:
    st.header("تولید محتوا")
    url = st.text_input("لینک یوتیوب:")
    if st.button("شروع پردازش"):
        st.success("درخواست ثبت شد (شبیه‌سازی)")
    
    try:
        ws_vid = sh.worksheet("Video_Factory")
        st.dataframe(pd.DataFrame(ws_vid.get_all_records()))
    except:
        pass

# --- تب ۳ و ۴ (ساده شده برای تست) ---
with tab_future:
    st.write("بخش آینده‌پژوهی")

with tab_config:
    st.write("تنظیمات")
