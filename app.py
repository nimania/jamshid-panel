import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- تنظیمات صفحه ---
st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

# --- اتصال به دیتابیس (روش تضمینی) ---
@st.cache_resource
def connect_to_db():
    try:
        # 1. دریافت اطلاعات از تنظیمات
        info = dict(st.secrets["gcp_service_account"])
        
        # 2. اصلاح فرمت کلید (باگ‌گیری خودکار)
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        
        # 3. تعریف سطح دسترسی (Scopes)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # 4. ساخت اعتبارنامه به روش استاندارد گوگل
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 5. باز کردن شیت
        return client.open("Command_Center")
        
    except Exception as e:
        st.error(f"❌ خطای اتصال: {e}")
        st.info("راهنما: لطفا چک کنید در فایل secrets.toml همه چیز داخل گیومه باشد.")
        st.stop()

# --- بدنه اصلی ---
sh = connect_to_db()
st.toast("اتصال موفق بود! ✅", icon="🚀")

st.title("👑 اتاق فرمان جمشید")

tab1, tab2 = st.tabs(["📰 اخبار", "⚙️ تنظیمات"])

with tab1:
    st.subheader("اخبار موجود در دیتابیس")
    try:
        ws = sh.worksheet("News_Feed")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    except:
        st.warning("تب News_Feed خالی است یا وجود ندارد.")

with tab2:
    st.write("تنظیمات فعال است.")
