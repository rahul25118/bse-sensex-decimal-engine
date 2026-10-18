import streamlit as st
import yfinance as yf
import pandas as pd
from collections import Counter
from datetime import datetime, time
import pytz

st.set_page_config(
    page_title="Pre-Close Decimal Engine (T-10 Min)",
    page_icon="⏱️",
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

st.title("⏱️ Pre-Close Closing Decimal Engine")
st.caption("क्लोजिंग से ठीक 10 मिनट पहले (T-10 Min Lock) 15-उम्मीदवारों की बास्केट")

@st.cache_data(ttl=60)
def fetch_market_data(ticker, tz_name):
    # केवल मुख्य इंडेक्स टिकर (^HSI और ^BSESN)
    df = yf.Ticker(ticker).history(period="60d", interval="2m")
    if df.empty or len(df) < 50:
        df = yf.Ticker(ticker).history(period="60d", interval="5m")
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(tz_name)
    else:
        df.index = df.index.tz_convert(tz_name)
        
    df["Date"] = df.index.date
    df["Decimal"] = df["Close"].apply(lambda x: f"{float(x):.2f}".split(".")[1].zfill(2))
    return df

def run_t10_engine(day_df, lock_time_str, core_start_str, late_start_str, low_k, high_k):
    lock_t = pd.to_datetime(lock_time_str).time()
    core_t = pd.to_datetime(core_start_str).time()
    late_t = pd.to_datetime(late_start_str).time()
    
    df_pre_lock = day_df[day_df.index.time <= lock_t]
    win_core = day_df[(day_df.index.time >= core_t) & (day_df.index.time <= lock_t)]
    win_late = day_df[(day_df.index.time >= late_t) & (day_df.index.time <= lock_t)]
    
    if df_pre_lock.empty:
        return None
        
    all_day_counts = Counter(df_pre_lock["Decimal"])
    core_counts = Counter(win_core["Decimal"])
    late_counts = Counter(win_late["Decimal"])
    
    repeaters = [k for k, v in core_counts.items() if v >= 2]
    window_uniques = [k for k, v in core_counts.items() if v == 1]
    confirmed_uniques = [k for k in window_uniques if all_day_counts.get(k, 0) >= 3]
    late_uniques = [k for k, v in late_counts.items() if v == 1]
    
    pool = list(dict.fromkeys(repeaters + confirmed_uniques + late_uniques))
    
    # अगर 03:50 तक टिक्स कम हों, तो दिन के अन्य टिक्स से 15 पूरे करें
    if len(pool) < 15:
        for d in df_pre_lock["Decimal"].tolist()[::-1]:
            if d not in pool:
                pool.append(d)
            if len(pool) == 15:
                break
                
    pool_sorted = sorted(pool, key=lambda x: int(x))
    
    lowest = pool_sorted[:low_k]
    highest = pool_sorted[-high_k:]
    final_15 = list(dict.fromkeys(lowest + highest))
    
    actual_close_price = day_df.iloc[-1]["Close"]
    actual_close_dec = day_df.iloc[-1]["Decimal"]
    is_market_closed = day_df.index[-1].time() > lock_t
    
    is_hit = False
    side = "PENDING"
    if is_market_closed:
        is_hit = actual_close_dec in final_15
        if is_hit:
            side = "🟢 LOW SIDE" if actual_close_dec in lowest else "🔴 HIGH SIDE"
        else:
            side = "❌ MISS"
            
    return {
        "price_at_lock": df_pre_lock.iloc[-1]["Close"],
        "actual_close_price": actual_close_price,
        "actual_close_dec": actual_close_dec,
        "lowest": lowest,
        "highest": highest,
        "final_15": final_15,
        "is_hit": is_hit,
        "is_closed": is_market_closed,
        "side": side,
        "pool_len": len(pool)
    }

tab_bse, tab_hsi = st.tabs(["🏛️ BSE Sensex (Lock @ 03:20 PM IST)", "🇭🇰 Hang Seng Index (Lock @ 03:50 PM HKT / 01:20 PM IST)"])

# BSE SENSEX
with tab_bse:
    now_ist = datetime.now(IST)
    bse_df = fetch_market_data("^BSESN", "Asia/Kolkata")
    bse_dates = sorted(bse_df["Date"].unique(), reverse=True)
    sel_bse_date = st.selectbox("तारीख चुनें (BSE):", bse_dates, key="bse_select_date")
    
    res_b = run_t10_engine(bse_df[bse_df["Date"] == sel_bse_date], "15:20:00", "14:00:00", "15:00:00", 8, 7)
    if res_b:
        st.markdown('<div class="lock-banner">🔒 03:20 PM IST पर लॉक की गई 15 बास्केट</div>', unsafe_allow_html=True)
        main_badges = "".join([
            f"<span class='badge-hit'>🎯 .{x} (HIT)</span>" if (res_b['is_closed'] and x == res_b['actual_close_dec'])
            else f"<span class='badge-main'>.{x}</span>"
            for x in res_b['final_15']
        ])
        st.markdown(main_badges, unsafe_allow_html=True)
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("03:20 PM लॉक भाव", f"{res_b['price_at_lock']:.2f}")
        m2.metric("03:30 PM क्लोज भाव", f"{res_b['actual_close_price']:.2f} (.{res_b['actual_close_dec']})")
        m3.metric("परिणाम", "✅ HIT" if res_b["is_hit"] else "❌ MISS", res_b["side"])

# HANG SENG INDEX (शुद्ध ^HSI इंडेक्स)
with tab_hsi:
    now_hkt = datetime.now(HKT)
    hsi_df = fetch_market_data("^HSI", "Asia/Hong_Kong")
    hsi_dates = sorted(hsi_df["Date"].unique(), reverse=True)
    sel_hsi_date = st.selectbox("तारीख चुनें (Hang Seng):", hsi_dates, key="hsi_select_date")
    
    res_h = run_t10_engine(hsi_df[hsi_df["Date"] == sel_hsi_date], "15:50:00", "14:30:00", "15:30:00", 9, 6)
    if res_h:
        st.markdown('<div class="lock-banner">🔒 03:50 PM HKT (01:20 PM IST) पर लॉक की गई 15 बास्केट</div>', unsafe_allow_html=True)
        main_badges_h = "".join([
            f"<span class='badge-hit'>🎯 .{x} (HIT)</span>" if (res_h['is_closed'] and x == res_h['actual_close_dec'])
            else f"<span class='badge-main'>.{x}</span>"
            for x in res_h['final_15']
        ])
        st.markdown(main_badges_h, unsafe_allow_html=True)
        
        c_low_h, c_high_h = st.columns(2)
        with c_low_h:
            st.markdown(f"**🟢 9 Lowest Candidates:**")
            st.markdown("".join([f"<span class='badge-low'>.{x}</span>" for x in res_h['lowest']]), unsafe_allow_html=True)
        with c_high_h:
            st.markdown(f"**🔴 6 Highest Candidates:**")
            st.markdown("".join([f"<span class='badge-high'>.{x}</span>" for x in res_h['highest']]), unsafe_allow_html=True)
            
        st.divider()
        mh1, mh2, mh3 = st.columns(3)
        mh1.metric("03:50 PM लॉक भाव (^HSI)", f"{res_h['price_at_lock']:.2f}")
        mh2.metric("04:08 PM क्लोज भाव (^HSI)", f"{res_h['actual_close_price']:.2f} (.{res_h['actual_close_dec']})")
        mh3.metric("परिणाम", "✅ HIT" if res_h["is_hit"] else "❌ MISS", res_h["side"])
