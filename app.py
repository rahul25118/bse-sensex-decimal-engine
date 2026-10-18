import streamlit as st
import yfinance as yf
import pandas as pd
from collections import Counter
from datetime import datetime, time
import pytz

st.set_page_config(page_title="Pre-Close Decimal Engine", page_icon="⏱️", layout="wide")

IST = pytz.timezone("Asia/Kolkata")
HKT = pytz.timezone("Asia/Hong_Kong")

st.title("⏱️ Pre-Close Closing Decimal Engine")
st.caption("शुद्ध इंडेक्स डेटा (^BSESN & ^HSI) - कोई ETF नहीं")

# कैश टाइम 1 सेकंड कर दिया ताकि पुराना डेटा कभी न दिखे
@st.cache_data(ttl=1)
def get_clean_data(symbol, tz):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="60d", interval="2m")
    if df.empty or len(df) < 20:
        df = ticker.history(period="60d", interval="5m")
    if df.empty:
        df = ticker.history(period="60d", interval="1d")
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(tz)
    else:
        df.index = df.index.tz_convert(tz)
    df["Date"] = df.index.date
    df["Decimal"] = df["Close"].apply(lambda x: f"{float(x):.2f}".split(".")[1].zfill(2))
    return df

tab_bse, tab_hsi = st.tabs(["🏛️ BSE Sensex", "🇭🇰 Hang Seng Index (^HSI)"])

with tab_bse:
    df_b = get_clean_data("^BSESN", "Asia/Kolkata")
    dates_b = sorted(df_b["Date"].unique(), reverse=True)
    d_b = st.selectbox("तारीख चुनें (BSE):", dates_b, key="b_sel")
    sub_b = df_b[df_b["Date"] == d_b]
    if not sub_b.empty:
        c1, c2 = st.columns(2)
        c1.metric("क्लोज भाव", f"{sub_b.iloc[-1]['Close']:.2f}")
        c2.metric("क्लोज दशमलव", f".{sub_b.iloc[-1]['Decimal']}")

with tab_hsi:
    # केवल और केवल ^HSI इंडेक्स
    df_h = get_clean_data("^HSI", "Asia/Hong_Kong")
    dates_h = sorted(df_h["Date"].unique(), reverse=True)
    d_h = st.selectbox("तारीख चुनें (Hang Seng ^HSI):", dates_h, key="h_sel")
    sub_h = df_h[df_h["Date"] == d_h]
    if not sub_h.empty:
        close_p = sub_h.iloc[-1]["Close"]
        close_d = sub_h.iloc[-1]["Decimal"]
        
        c1, c2 = st.columns(2)
        c1.metric("आधिकारिक ^HSI क्लोज", f"{close_p:.2f}")
        c2.metric("क्लोज दशमलव", f".{close_d}")
        
        pool = list(dict.fromkeys(sub_h["Decimal"].tolist()))
        pool_sorted = sorted(pool, key=lambda x: int(x))
        low9 = pool_sorted[:9]
        high6 = pool_sorted[-6:]
        b15 = list(dict.fromkeys(low9 + high6))
        
        st.subheader("🎯 15 उम्मीदवारों की बास्केट")
        st.write(" ".join([f"` .{x} `" for x in b15]))
        if close_d in b15:
            st.success(f"🎯 HIT: क्लोज दशमलव .{close_d} बास्केट में मौजूद है!")
        else:
            st.error(f"❌ MISS: क्लोज दशमलव .{close_d} बास्केट से बाहर है")
