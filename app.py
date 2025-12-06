import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

@st.cache_resource
def connect_to_db():
    try:
        # دریافت مستقیم اطلاعات از فرمت استاندارد
        # .copy() is used to avoid modifying the streamlit secrets object in place
        info = dict(st.secrets["gcp_service_account"]).copy()
        
        # حل مشکل خطوط جدید در کلید خصوصی
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
            
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open("Command_Center")
        
    except Exception as e:
        st.error(f"❌ خطای اتصال: {e}")
        st.stop()

# اجرای برنامه
sh = connect_to_db()
st.toast("جمشید متصل شد! 🚀", icon="✅")

st.title("👑 اتاق فرمان جمشید")

tab1, tab2 = st.tabs(["📰 اخبار", "⚙️ تنظیمات"])

with tab1:
    try:
        ws = sh.worksheet("News_Feed")
        st.dataframe(pd.DataFrame(ws.get_all_records()), use_container_width=True)
    except:
        st.info("دیتابیس متصل است (News_Feed خالی است).")

with tab2:
    st.write("تنظیمات")
