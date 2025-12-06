import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import feedparser
import yt_dlp
from openai import OpenAI
import json
from datetime import datetime

st.set_page_config(page_title="Jamshid Panel", page_icon="👑", layout="wide")

# --- 1. اتصال به دیتابیس ---
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
        st.error(f"❌ خطای دیتابیس: {e}")
        st.stop()

sh = connect_to_db()

# --- 2. تابع نویسنده (ChatGPT) ---
def generate_script_gpt(text, project_type):
    if not text: return "متنی وجود ندارد."
    
    try:
        client = OpenAI(api_key=st.secrets["openai"]["api_key"])
        
        if project_type == "پاورقی (سریال ترکی)":
            system_msg = "تو یک نویسنده خلاق یوتیوب هستی. متن زیرنویس را به یک سناریوی فارسی جذاب، داستان‌گو و صمیمی (Storytelling) تبدیل کن. ساختار: مقدمه (قلاب)، بدنه داستان (۳ اتفاق مهم)، پایان‌بندی."
        else:
            system_msg = "تو یک تحلیلگر سیاسی استراتژیک هستی. جان کلام متن زیر را استخراج کن: خلاصه مدیریتی، ۳ نکته کلیدی، نتیجه‌گیری و پیش‌بینی آینده."

        response = client.chat.completions.create(
            model="gpt-4o-mini", # مدل سریع و ارزان (یا gpt-3.5-turbo)
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"متن ورودی:\n{text[:15000]}"}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"خطای OpenAI: {e}"

# --- 3. توابع کمکی ---
def fetch_rss_feed(rss_url):
    try:
        feed = feedparser.parse(rss_url)
        return [[datetime.now().strftime("%Y-%m-%d %H:%M"), feed.feed.get('title', 'Unknown'), entry.title, entry.link, "New"] for entry in feed.entries[:5]]
    except: return []

def download_transcript_heavy(url):
    try:
        ydl_opts = {'skip_download': True, 'writesubtitles': True, 'writeautomaticsub': True, 'subtitleslangs': ['fa','en','tr'], 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'subtitles' in info and info['subtitles']: return "زیرنویس رسمی یافت شد."
            if 'automatic_captions' in info: return "زیرنویس اتوماتیک یافت شد."
        return None
    except: return None

# --- 4. رابط کاربری ---
st.title("👑 اتاق فرمان جمشید (موتور OpenAI)")
tab_news, tab_video, tab_config = st.tabs(["📰 اتاق خبر", "🎬 کارخانه ویدئو", "⚙️ تنظیمات"])

with tab_news:
    if st.button("🔄 بروزرسانی اخبار"):
        ws_conf = sh.worksheet("Config")
        new_news = []
        for item in ws_conf.get_all_records():
            if item['Type'] == 'RSS' and item['Value']:
                new_news.extend(fetch_rss_feed(item['Value']))
        if new_news:
            sh.worksheet("News_Feed").append_rows([n + [""] for n in new_news])
            st.success("اخبار جدید رسید!")
            st.rerun()
    try: st.dataframe(pd.DataFrame(sh.worksheet("News_Feed").get_all_records()), use_container_width=True)
    except: pass

with tab_video:
    st.header("۱. ورودی")
    with st.form("input_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            v_url = st.text_input("لینک یوتیوب:")
            manual = st.text_area("متن دستی:", height=100)
        with col2:
            p_name = st.text_input("نام پروژه:")
            p_type = st.selectbox("نوع:", ["پاورقی (سریال ترکی)", "جان کلام (تحلیلی)"])
            voice = st.selectbox("صدا:", ["Nima (Clone)", "Adam"])
        
        if st.form_submit_button("ثبت"):
            sub_text = manual if manual else (download_transcript_heavy(v_url) if v_url else "")
            if sub_text:
                final_name = p_name if p_name.strip() else f"پروژه {datetime.now().strftime('%H:%M:%S')}"
                sh.worksheet("Video_Factory").append_row([final_name, v_url, sub_text, "", voice, "Ready for AI", ""])
                st.success("ثبت شد!")
                st.rerun()
            else: st.error("متن یا لینک معتبر وارد کنید.")

    st.divider()
    st.header("۲. اتاق نویسندگان (ChatGPT) ✍️")
    
    try:
        ws_vid = sh.worksheet("Video_Factory")
        df_vid = pd.DataFrame(ws_vid.get_all_records())
        
        if not df_vid.empty:
            # فیلتر کردن پروژه‌های ناتمام
            pending = df_vid[df_vid['Script'] == ""].reset_index()
            
            if not pending.empty:
                # اصلاح باگ نمایش سفید: اگر اسم خالی بود، یک اسم موقت نشان بده
                def get_label(x):
                    name = str(pending.loc[x, 'Project_Name']).strip()
                    return name if name else f"پروژه بدون نام (ردیف {x+1})"

                sel_idx = st.selectbox("انتخاب پروژه:", pending.index, format_func=get_label)
                sel_row = pending.loc[sel_idx]
                
                if st.button("✨ نوشتن سناریو"):
                    with st.spinner("ChatGPT در حال نوشتن..."):
                        res = generate_script_gpt(sel_row['Subtitle_Text'], "پاورقی (سریال ترکی)")
                        
                        if "خطا" not in res:
                            cell = ws_vid.find(sel_row['Project_Name'])
                            ws_vid.update_cell(cell.row, 4, res)
                            ws_vid.update_cell(cell.row, 6, "Script Done")
                            st.success("تمام شد!")
                            st.text_area("خروجی:", res, height=300)
                            st.rerun()
                        else: st.error(res)
            else: st.info("پروژه جدیدی برای نوشتن نیست.")
        st.dataframe(df_vid, use_container_width=True)
    except Exception as e: st.write(f"وضعیت: {e}")

with tab_config:
    try: st.dataframe(pd.DataFrame(sh.worksheet("Config").get_all_records()))
    except: pass
