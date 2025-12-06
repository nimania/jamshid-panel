import streamlit as st
import pandas as pd
import gspread

# --- تنظیمات صفحه ---
st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

# --- اتصال به دیتابیس (نسخه ضد گلوله) ---
@st.cache_resource
def connect_to_db():
    try:
        # دریافت اطلاعات از تنظیمات مخفی
        credentials = dict(st.secrets["gcp_service_account"])
        
        # این خط جادویی، مشکل فرمت کلید را حل می‌کند
        credentials["private_key"] = credentials["private_key"].replace("\\n", "\n")

        # اتصال مستقیم و ساده
        gc = gspread.service_account_from_dict(credentials)
        return gc.open("Command_Center")
        
    except Exception as e:
        st.error(f"❌ خطای اتصال: {e}")
        st.info("راهنما: لطفا چک کنید اسم فایل گوگل شیت دقیقاً Command_Center باشد و ربات به آن دسترسی داشته باشد.")
        st.stop()

# --- شروع سیستم ---
sh = connect_to_db()
st.toast("جمشید متصل شد! 🚀", icon="✅")

st.title("👑 اتاق فرمان جمشید")

# تب‌ها
tab1, tab2 = st.tabs(["📰 اخبار", "⚙️ تنظیمات"])

with tab1:
    st.header("لیست اخبار")
    try:
        ws = sh.worksheet("News_Feed")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    except:
        st.warning("تب News_Feed در گوگل شیت پیدا نشد.")

with tab2:
    st.write("تنظیمات سیستم فعال است.")
