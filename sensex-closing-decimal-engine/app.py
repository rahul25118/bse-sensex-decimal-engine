import streamlit as st
import yfinance as yf
import pandas as pd
from collections import Counter
from datetime import datetime, time
import pytz

st.set_page_config(
    page_title="Pre-Close Decimal Engine",
    page_icon="🎯",
    layout="wide"
)

IST = pytz.timezone("Asia/Kolkata")
HKT = pytz.timezone("Asia/Hong_Kong")

st.markdown("""
<style>
    .lock-banner {
        background-color: #d4edda;
        border: 2px solid #28a745;
        border-radius: 10px;
        padding: 12px 20px;
        color: #155724;
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 15px;
    }
    .waiting-banner {
        background-color: #fff3cd;
        border: 2px solid #ffeeba;
        border-radius: 10px;
        padding: 12px 20px;
        color: #856404;
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 15px;
    }
    .badge-main {
        display: inline-block;
        background-color: #e8f0fe;
        color: #1a73e8;
        padding: 8px 14px;
        border-radius: 8px;
        font-weight: bold;
        margin: 4px;
        font-size: 20px;
        border: 2px solid #1a73e8;
    }
    .badge-hit {
        display: inline-block;
        background-color: #28a745;
        color: #ffffff;
        padding: 8px 14px;
        border-radius: 8px;
        font-weight: bold;
        margin: 4px;
        font-size: 20px;
        border: 2px solid #1e7e34;
    }
    .badge-low {
        display: inline-block;
        background-color: #e6f4ea;
        color: #137333;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        margin: 2px;
        font-size: 15px;
    }
    .badge-high {
        display: inline-block;
        background-color: #fce8e6;
        color: #c5221f;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        margin: 2px;
        font-size: 15px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Pre-Close Decimal Engine (T-10 Min Lock)")
st.caption("BSE Sensex (8 Low + 7 High) & Hang Seng Index (9 Low + 6 High)")

# ---------------------------------------------------------
# डेटा फ़ेचिंग: शुद्ध इंडेक्स (^BSESN & ^HSI)
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def fetch_clean_index(symbol, tz_str):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="60d", interval="2m")
    
    # 2m डेटा अधूरा होने पर 5m से पूरक करें
    if df.empty or len(df) < 30:
        df = ticker.history(period="60d", interval="5m")
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(tz_str)
    else:
        df.index = df.index.tz_convert(tz_str)
        
    df["Date"] = df.index.date
    df["Decimal"] = df["Close"].apply(lambda x: f"{float(x):.2f}".split(".")[1].zfill(2))
    
    # आधिकारिक दैनिक समापन भाव (Official Daily Settlement)
    df_daily = ticker.history(period="60d", interval="1d")
    daily_closes = {}
    if not df_daily.empty:
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)
        for d, row in df_daily.iterrows():
            daily_closes[d.date()] = (row["Close"], f"{float(row['Close']):.2f}".split(".")[1].zfill(2))
            
    return df, daily_closes

# ---------------------------------------------------------
# कोर बारबेल इंजन (Barbell Barcoding)
# ---------------------------------------------------------
def run_engine(day_df, official_close_tuple, lock_str, core_start_str, late_start_str, low_k, high_k):
    lock_t = pd.to_datetime(lock_str).time()
    core_t = pd.to_datetime(core_start_str).time()
    late_t = pd.to_datetime(late_start_str).time()
    
    df_pre = day_df[day_df.index.time <= lock_t]
    win_core = day_df[(day_df.index.time >= core_t) & (day_df.index.time <= lock_t)]
    win_late = day_df[(day_df.index.time >= late_t) & (day_df.index.time <= lock_t)]
    
    if df_pre.empty:
        return None
        
    all_day_counts = Counter(df_pre["Decimal"])
    core_counts = Counter(win_core["Decimal"])
    late_counts = Counter(win_late["Decimal"])
    
    # 1. कोर रिपीटर्स (विंडो में >= 2x)
    repeaters = [k for k, v in core_counts.items() if v >= 2]
    # 2. डे-कन्फर्म्ड यूनिक (विंडो में 1x, दिनभर में >= 3x)
    uniques = [k for k, v in core_counts.items() if v == 1]
    confirmed = [k for k in uniques if all_day_counts.get(k, 0) >= 3]
    # 3. लेट यूनिक (अंतिम 20 मिनट में ताज़ा 1x)
    late_u = [k for k, v in late_counts.items() if v == 1]
    
    pool = list(dict.fromkeys(repeaters + confirmed + late_u))
    
    # पूल को सख्त 15 तक पूरा करना (यदि टिक्स कम हों)
    if len(pool) < 15:
        for d in df_pre["Decimal"].tolist()[::-1]:
            if d not in pool:
                pool.append(d)
            if len(pool) == 15:
                break
                
    # छोटे से बड़ा (Ascending Order)
    pool_sorted = sorted(pool, key=lambda x: int(x))
    
    lowest = pool_sorted[:low_k]
    highest = pool_sorted[-high_k:]
    final_15 = list(dict.fromkeys(lowest + highest))
    
    # क्लोजिंग प्राइस और दशमलव तय करना
    if official_close_tuple:
        actual_price, actual_dec = official_close_tuple
    else:
        actual_price = day_df.iloc[-1]["Close"]
        actual_dec = day_df.iloc[-1]["Decimal"]
        
    is_market_closed = day_df.index[-1].time() > lock_t
    
    is_hit = False
    side = "PENDING"
    if is_market_closed:
        is_hit = actual_dec in final_15
        if is_hit:
            side = "🟢 LOW SIDE" if actual_dec in lowest else "🔴 HIGH SIDE"
        else:
            side = "❌ MISS"
            
    return {
        "price_at_lock": df_pre.iloc[-1]["Close"],
        "actual_price": actual_price,
        "actual_dec": actual_dec,
        "lowest": lowest,
        "highest": highest,
        "final_15": final_15,
        "is_hit": is_hit,
        "is_closed": is_market_closed,
        "side": side
    }

# ---------------------------------------------------------
# टैब्स
# ---------------------------------------------------------
tab_bse, tab_hsi = st.tabs([
    "🏛️ BSE Sensex (8 Low + 7 High)",
    "🇭🇰 Hang Seng Index (9 Low + 6 High)"
])

# TAB 1: BSE SENSEX
with tab_bse:
    now_ist = datetime.now(IST)
    bse_df, bse_daily = fetch_clean_index("^BSESN", "Asia/Kolkata")
    bse_dates = sorted(bse_df["Date"].unique(), reverse=True)
    
    col_d, col_c = st.columns([2, 1])
    with col_d:
        sel_bse_date = st.selectbox("तारीख चुनें (BSE Sensex):", bse_dates, key="bse_final_date")
    with col_c:
        st.metric("वर्तमान IST समय", now_ist.strftime("%I:%M:%S %p"))
        
    res_b = run_engine(
        bse_df[bse_df["Date"] == sel_bse_date],
        bse_daily.get(sel_bse_date),
        lock_str="15:20:00",
        core_start_str="14:00:00",
        late_start_str="15:00:00",
        low_k=8,
        high_k=7
    )
    
    if res_b:
        if sel_bse_date == now_ist.date() and now_ist.time() < time(15, 20):
            st.markdown('<div class="waiting-banner">⏳ लाइव मार्केट चालू है। 03:20 PM IST पर 15 नंबर लॉक होंगे।</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="lock-banner">🔒 03:20 PM IST पर लॉक की गई 15 बास्केट (8 Low + 7 High)</div>', unsafe_allow_html=True)
            
        st.subheader("🎯 15 उम्मीदवारों की मुख्य बास्केट (BSE Sensex)")
        badges_b = "".join([
            f"<span class='badge-hit'>🎯 .{x} (HIT)</span>" if (res_b['is_closed'] and x == res_b['actual_dec'])
            else f"<span class='badge-main'>.{x}</span>"
            for x in res_b['final_15']
        ])
        st.markdown(badges_b, unsafe_allow_html=True)
        
        cl_b, ch_b = st.columns(2)
        with cl_b:
            st.markdown(f"**🟢 8 Lowest Candidates:**")
            st.markdown("".join([f"<span class='badge-low'>.{x}</span>" for x in res_b['lowest']]), unsafe_allow_html=True)
        with ch_b:
            st.markdown(f"**🔴 7 Highest Candidates:**")
            st.markdown("".join([f"<span class='badge-high'>.{x}</span>" for x in res_b['highest']]), unsafe_allow_html=True)
            
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("03:20 PM लॉक भाव", f"{res_b['price_at_lock']:.2f}")
        if res_b["is_closed"]:
            m2.metric("03:30 PM आधिकारिक क्लोज", f"{res_b['actual_price']:.2f} (.{res_b['actual_dec']})")
            m3.metric("परिणाम", "✅ HIT" if res_b["is_hit"] else "❌ MISS", res_b["side"])
        else:
            m2.metric("03:30 PM क्लोज भाव", "ऑक्शन में...")
            m3.metric("परिणाम", "प्रतीक्षा में")
    else:
        st.warning("BSE Sensex का डेटा उपलब्ध नहीं है।")

# TAB 2: HANG SENG INDEX
with tab_hsi:
    now_hkt = datetime.now(HKT)
    hsi_df, hsi_daily = fetch_clean_index("^HSI", "Asia/Hong_Kong")
    hsi_dates = sorted(hsi_df["Date"].unique(), reverse=True)
    
    col_dh, col_ch = st.columns([2, 1])
    with col_dh:
        sel_hsi_date = st.selectbox("तारीख चुनें (Hang Seng Index):", hsi_dates, key="hsi_final_date")
    with col_ch:
        st.metric("वर्तमान HKT समय", now_hkt.strftime("%I:%M:%S %p"))
        
    res_h = run_engine(
        hsi_df[hsi_df["Date"] == sel_hsi_date],
        hsi_daily.get(sel_hsi_date),
        lock_str="15:50:00",
        core_start_str="14:30:00",
        late_start_str="15:30:00",
        low_k=9,
        high_k=6
    )
    
    if res_h:
        if sel_hsi_date == now_hkt.date() and now_hkt.time() < time(15, 50):
            st.markdown('<div class="waiting-banner">⏳ लाइव मार्केट चालू है। 03:50 PM HKT (01:20 PM IST) पर 15 नंबर लॉक होंगे।</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="lock-banner">🔒 03:50 PM HKT (01:20 PM IST) पर लॉक की गई 15 बास्केट (9 Low + 6 High)</div>', unsafe_allow_html=True)
            
        st.subheader("🎯 15 उम्मीदवारों की मुख्य बास्केट (Hang Seng ^HSI)")
        badges_h = "".join([
            f"<span class='badge-hit'>🎯 .{x} (HIT)</span>" if (res_h['is_closed'] and x == res_h['actual_dec'])
            else f"<span class='badge-main'>.{x}</span>"
            for x in res_h['final_15']
        ])
        st.markdown(badges_h, unsafe_allow_html=True)
        
        cl_h, ch_h = st.columns(2)
        with cl_h:
            st.markdown(f"**🟢 9 Lowest Candidates:**")
            st.markdown("".join([f"<span class='badge-low'>.{x}</span>" for x in res_h['lowest']]), unsafe_allow_html=True)
        with ch_h:
            st.markdown(f"**🔴 6 Highest Candidates:**")
            st.markdown("".join([f"<span class='badge-high'>.{x}</span>" for x in res_h['highest']]), unsafe_allow_html=True)
            
        st.divider()
        mh1, mh2, mh3 = st.columns(3)
        mh1.metric("03:50 PM लॉक भाव (^HSI)", f"{res_h['price_at_lock']:.2f}")
        if res_h["is_closed"]:
            mh2.metric("04:08 PM आधिकारिक क्लोज (^HSI)", f"{res_h['actual_price']:.2f} (.{res_h['actual_dec']})")
            mh3.metric("परिणाम", "✅ HIT" if res_h["is_hit"] else "❌ MISS", res_h["side"])
        else:
            mh2.metric("04:08 PM क्लोज भाव", "ऑक्शन में...")
            mh3.metric("परिणाम", "प्रतीक्षा में")
    else:
        st.warning("Hang Seng Index (^HSI) का डेटा लोड नहीं हो सका।")
