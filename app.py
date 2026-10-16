import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

st.set_page_config(page_title="BSE Sensex Decimal Engine", layout="wide")

st.title("🏛️ BSE SENSEX Decimal Frequency & Closing Engine")
st.caption("03:00–03:20 PM IST विंडो: रिपीटेड (कॉमन), यूनिक और अनसीन अंकों का 03:30 PM क्लोजिंग से मिलान।")

ist = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(ist)
st.sidebar.info(f"🕒 वर्तमान समय (IST): {now_ist.strftime('%Y-%m-%d %H:%M:%S')}")

# टिकर और सेटिंग्स (BSE Sensex)
TICKER = "^BSESN"
BACKUP_TICKER = "SENSEXBEES.NS"
TOTAL_POSSIBLE = 20
ALL_POSSIBLE = [f"{x * 5:02d}" for x in range(20)]

WIN_START = "15:00:00"
WIN_END = "15:20:00"
CLOSE_TARGET_TIME = "15:28:00"

@st.cache_data(ttl=60)
def fetch_bse_data():
    df = yf.Ticker(TICKER).history(period="30d", interval="2m")
    if df.empty or len(df) < 50:
        df = yf.Ticker(BACKUP_TICKER).history(period="30d", interval="2m")
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    df["Date"] = df.index.date
    df["Decimal"] = df["Close"].apply(lambda x: f"{float(x):.2f}".split(".")[1].zfill(2))
    return df

df_all = fetch_bse_data()

if df_all.empty:
    st.error("BSE Sensex का डेटा लोड नहीं हो सका। कृपया बाद में प्रयास करें।")
    st.stop()

available_dates = sorted(df_all["Date"].unique(), reverse=True)
selected_date = st.sidebar.selectbox("📅 तारीख चुनें:", available_dates, index=0)

day_df = df_all[df_all["Date"] == selected_date].copy()
win_df = day_df.between_time(WIN_START, WIN_END).copy()

st.sidebar.markdown("---")
st.sidebar.write("**विंडो विवरण:**")
st.sidebar.write("• विश्लेषण विंडो: `03:00 - 03:20 PM IST`")
st.sidebar.write("• क्लोजिंग ऑक्शन: `03:30 PM IST`")
st.sidebar.write("• कुल संभव दशमलव: `20 अंक (.00, .05, ... .95)`")

if len(win_df) < 3:
    st.warning("⚠️ 03:00–03:20 PM विंडो का पर्याप्त डेटा उपलब्ध नहीं है।")
else:
    counts = win_df["Decimal"].value_counts()
    common_pool = counts[counts >= 2]  # ज्यादा रिपीटेड अंक
    unique_pool = counts[counts == 1]  # केवल 1 बार आए अंक
    seen_set = set(counts.index)
    unseen_pool = sorted(list(set(ALL_POSSIBLE) - seen_set))

    # 1. मेट्रिक्स कार्ड्स
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("🔄 रिपीटेड (कॉमन) अंक", f"{len(common_pool)} अंक", delta=">= 2 बार आए")
    with m2:
        st.metric("⚡ यूनिक अंक", f"{len(unique_pool)} अंक", delta="सिर्फ 1 बार आया")
    with m3:
        st.metric("🚫 अनसीन (बाहर) अंक", f"{len(unseen_pool)} अंक", delta="0 बार (विंडो से बाहर)", delta_color="inverse")

    st.markdown("---")

    # 2. पूल्स विवरण
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔄 ज्यादा रिपीटेड (Common)")
        st.caption("03:00–03:20 के बीच 2 या अधिक बार आए:")
        if not common_pool.empty:
            for dec, cnt in common_pool.items():
                st.write(f"• **.{dec}** — ({cnt} बार)")
        else:
            st.write("कोई अंक रिपीट नहीं हुआ।")

    with c2:
        st.subheader("⚡ यूनिक अंक (Unique)")
        st.caption("03:00–03:20 के बीच ठीक 1 बार आया:")
        if not unique_pool.empty:
            st.write(", ".join([f"`.{x}`" for x in sorted(unique_pool.index)]))
        else:
            st.write("कोई यूनिक अंक नहीं मिला।")

    with c3:
        st.subheader("🚫 अनसीन अंक (Unseen)")
        st.caption("विंडो में एक बार भी नहीं दिखा:")
        st.write(", ".join([f"`.{x}`" for x in unseen_pool]))

    st.markdown("---")

    # 3. 03:30 PM क्लोजिंग मैच
    target_time = datetime.strptime(CLOSE_TARGET_TIME, "%H:%M:%S").time()
    bars_before_target = day_df[day_df.index.time <= target_time]

    if not bars_before_target.empty and len(bars_before_target) >= 15:
        close_bar = bars_before_target.iloc[-1]
        close_price = close_bar["Close"]
        close_dec = close_bar["Decimal"]
        close_time = close_bar.name.strftime("%H:%M:%S")

        if close_dec in common_pool.index:
            cnt_val = common_pool.get(close_dec)
            st.success(f"**03:30 PM क्लोजिंग भाव ({close_time} IST):** {close_price:.2f} (दशमलव: **.{close_dec}**) | **परिणाम:** ✅ रिपीटेड (Common) पूल में मैच हुआ! (विंडो में {cnt_val} बार आया था)")
        elif close_dec in unique_pool.index:
            st.info(f"**03:30 PM क्लोजिंग भाव ({close_time} IST):** {close_price:.2f} (दशमलव: **.{close_dec}**) | **परिणाम:** 🔵 यूनिक (Unique) पूल में आया (विंडो में 1 बार दिखा था)")
        else:
            st.error(f"**03:30 PM क्लोजिंग भाव ({close_time} IST):** {close_price:.2f} (दशमलव: **.{close_dec}**) | **परिणाम:** ❌ अनसीन (Unseen) पूल में गया (03:00-03:20 विंडो के बाहर बंद हुआ)")
    else:
        st.info("ℹ️ बाजार अभी खुला है या 03:30 PM की क्लोजिंग दर्ज नहीं हुई है।")

# 4. ऐतिहासिक ऑडिट टेबल (पिछले उपलब्ध दिन)
st.markdown("---")
st.subheader("📋 BSE Sensex: ऐतिहासिक 03:00–03:20 PM ऑडिट और क्लोजिंग मिलान")

history_rows = []
for d in available_dates:
    d_df = df_all[df_all["Date"] == d].copy()
    w_df = d_df.between_time(WIN_START, WIN_END).copy()
    target_bars = d_df[d_df.index.time <= datetime.strptime(CLOSE_TARGET_TIME, "%H:%M:%S").time()]

    if len(w_df) < 3 or target_bars.empty:
        continue

    c_bar = target_bars.iloc[-1]
    c_price = c_bar["Close"]
    c_dec = c_bar["Decimal"]

    w_counts = w_df["Decimal"].value_counts()
    c_common = w_counts[w_counts >= 2]
    c_unique = w_counts[w_counts == 1]

    if c_dec in c_common.index:
        outcome = f"✅ रिपीटेड ({c_common.get(c_dec)}x)"
    elif c_dec in c_unique.index:
        outcome = "🔵 यूनिक (1x)"
    else:
        outcome = "❌ अनसीन (0x)"

    history_rows.append({
        "तारीख": str(d),
        "क्लोजिंग भाव": f"{c_price:.2f}",
        "क्लोज दशमलव": f".{c_dec}",
        "रिपीटेड अंक संख्या": len(c_common),
        "यूनिक अंक संख्या": len(c_unique),
        "नतीजा": outcome
    })

if history_rows:
    st.dataframe(pd.DataFrame(history_rows), use_container_width=True)
