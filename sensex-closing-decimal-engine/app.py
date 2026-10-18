import streamlit as st
import yfinance as yf
import pandas as pd
from collections import defaultdict
from datetime import datetime, time
import pytz

st.set_page_config(
    page_title="Weighted Pre-Close Decimal Engine",
    page_icon="⚖️",
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
    .badge-top {
        display: inline-block;
        background-color: #fff0f5;
        color: #d63384;
        padding: 6px 12px;
        border-radius: 8px;
        font-weight: bold;
        margin: 3px;
        font-size: 16px;
        border: 2px solid #d63384;
    }
    .badge-main {
        display: inline-block;
        background-color: #e8f0fe;
        color: #1a73e8;
        padding: 6px 12px;
        border-radius: 8px;
        font-weight: bold;
        margin: 3px;
        font-size: 17px;
        border: 1px solid #1a73e8;
    }
    .badge-hit {
        display: inline-block;
        background-color: #28a745;
        color: #ffffff;
        padding: 6px 12px;
        border-radius: 8px;
        font-weight: bold;
        margin: 3px;
        font-size: 17px;
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
        font-size: 14px;
    }
    .badge-high {
        display: inline-block;
        background-color: #fce8e6;
        color: #c5221f;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        margin: 2px;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚖️ Time-Decay Weighted Decimal Engine")
st.caption("09:15-12:00 (1x) | 12:00-02:00 (2x) | 02:00-03:20 (4x Recency Decay) + Barbell Barcoding")

@st.cache_data(ttl=30)
def fetch_market_data(ticker, tz_name):
    df = yf.Ticker(ticker).history(period="60d", interval="2m")
    if df.empty or len(df) < 20:
        if ticker == "^BSESN":
            df = yf.Ticker("SETFBSE.NS").history(period="60d", interval="2m")
        elif ticker == "^HSI":
            df = yf.Ticker("^HSI").history(period="60d", interval="5m")
            
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(tz_name)
    else:
        df.index = df.index.tz_convert(tz_name)
        
    df["Date"] = df.index.date
    df["Decimal"] = df["Close"].apply(lambda x: f"{float(x):.2f}".split(".")[1].zfill(2))
    return df

def run_weighted_engine(day_df, lock_time_str, mid_time_str, core_time_str, low_k, high_k):
    lock_t = pd.to_datetime(lock_time_str).time()
    mid_t = pd.to_datetime(mid_time_str).time()
    core_t = pd.to_datetime(core_time_str).time()
    
    df_pre = day_df[day_df.index.time <= lock_t]
    if len(df_pre) < 10:
        return None
        
    # टाइम-डिके वेटेड स्कोरिंग
    scores = defaultdict(float)
    raw_counts = defaultdict(int)
    
    for idx, row in df_pre.iterrows():
        t = idx.time()
        dec = row["Decimal"]
        raw_counts[dec] += 1
        if t < mid_t:
            scores[dec] += 1.0   # सुबह (1x)
        elif t < core_t:
            scores[dec] += 2.0   # दोपहर (2x)
        else:
            scores[dec] += 4.0   # कोर क्लोजिंग रन-अप (4x)
            
    # 1. टॉप 3 वेटेड रिपीटर्स
    sorted_by_weight = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_3_anchors = [k for k, v in sorted_by_weight[:3]]
    
    # 2. बाकी बचे हुए अंकों का पूल
    remaining_pool = [k for k, v in sorted_by_weight if k not in top_3_anchors]
    pool_sorted = sorted(remaining_pool, key=lambda x: int(x))
    
    lowest = pool_sorted[:low_k]
    highest = pool_sorted[-high_k:]
    
    final_15 = list(dict.fromkeys(top_3_anchors + lowest + highest))
    if len(final_15) < 15:
        for x in pool_sorted:
            if x not in final_15:
                final_15.append(x)
            if len(final_15) == 15:
                break
                
    actual_close_price = day_df.iloc[-1]["Close"]
    actual_close_dec = day_df.iloc[-1]["Decimal"]
    is_market_closed = day_df.index[-1].time() > lock_t
    
    is_hit = False
    side = "PENDING"
    if is_market_closed:
        is_hit = actual_close_dec in final_15
        if is_hit:
            if actual_close_dec in top_3_anchors:
                side = "⭐ TOP 3 WEIGHTED"
            elif actual_close_dec in lowest:
                side = "🟢 LOW SIDE"
            else:
                side = "🔴 HIGH SIDE"
        else:
            side = "❌ MISS"
            
    return {
        "price_at_lock": df_pre.iloc[-1]["Close"],
        "actual_close_price": actual_close_price,
        "actual_close_dec": actual_close_dec,
        "top_3": top_3_anchors,
        "lowest": lowest,
        "highest": highest,
        "final_15": final_15,
        "is_hit": is_hit,
        "is_closed": is_market_closed,
        "side": side,
        "scores": scores,
        "raw_counts": raw_counts
    }

tab_bse, tab_hsi = st.tabs(["🏛️ BSE Sensex (Weighted Decay)", "🇭🇰 Hang Seng Index (^HSI Weighted)"])

# ---------------------------------------------------------
# TAB 1: BSE SENSEX
# ---------------------------------------------------------
with tab_bse:
    now_ist = datetime.now(IST)
    bse_df = fetch_market_data("^BSESN", "Asia/Kolkata")
    bse_dates = sorted(bse_df["Date"].unique(), reverse=True)
    
    c_d, c_t = st.columns([2, 1])
    with c_d:
        sel_bse_date = st.selectbox("तारीख चुनें (BSE):", bse_dates, key="bse_weighted_date")
    with c_t:
        st.metric("वर्तमान समय (IST)", now_ist.strftime("%I:%M:%S %p"))
        
    res_b = run_weighted_engine(
        bse_df[bse_df["Date"] == sel_bse_date],
        lock_time_str="15:20:00",
        mid_time_str="12:00:00",
        core_time_str="14:00:00",
        low_k=6,
        high_k=6
    )
    
    if res_b:
        if sel_bse_date == now_ist.date() and now_ist.time() < time(15, 20):
            st.markdown('<div class="waiting-banner">⏳ लाइव मार्केट: ठीक 03:20 PM IST पर वेटेड बास्केट लॉक होगी।</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="lock-banner">🔒 03:20 PM IST पर लॉक की गई 15 बास्केट (Time-Decay Weighted)</div>', unsafe_allow_html=True)
            
        st.subheader("🎯 आज की 15 बास्केट (Top 3 Weighted + 6 Low + 6 High)")
        badges = "".join([
            f"<span class='badge-hit'>🎯 .{x} (HIT)</span>" if (res_b['is_closed'] and x == res_b['actual_close_dec'])
            else f"<span class='badge-main'>.{x}</span>"
            for x in res_b['final_15']
        ])
        st.markdown(badges, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**⭐ टॉप 3 वेटेड रिपीटर्स:**")
            st.markdown("".join([f"<span class='badge-top'>.{x} ({res_b['scores'][x]:.0f} pts)</span>" for x in res_b['top_3']]), unsafe_allow_html=True)
        with c2:
            st.markdown("**🟢 6 Lowest Barcode:**")
            st.markdown("".join([f"<span class='badge-low'>.{x}</span>" for x in res_b['lowest']]), unsafe_allow_html=True)
        with c3:
            st.markdown("**🔴 6 Highest Barcode:**")
            st.markdown("".join([f"<span class='badge-high'>.{x}</span>" for x in res_b['highest']]), unsafe_allow_html=True)
            
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("03:20 PM लॉक भाव", f"{res_b['price_at_lock']:.2f}")
        if res_b["is_closed"]:
            m2.metric("03:30 PM क्लोज भाव", f"{res_b['actual_close_price']:.2f} (.{res_b['actual_close_dec']})")
            m3.metric("परिणाम", "✅ HIT" if res_b["is_hit"] else "❌ MISS", res_b["side"])
        else:
            m2.metric("03:30 PM क्लोज भाव", "ऑक्शन में...")
            m3.metric("परिणाम", "प्रतीक्षा में")
    else:
        st.warning("डेटा उपलब्ध नहीं है।")

# ---------------------------------------------------------
# TAB 2: HANG SENG INDEX
# ---------------------------------------------------------
with tab_hsi:
    now_hkt = datetime.now(HKT)
    hsi_df = fetch_market_data("^HSI", "Asia/Hong_Kong")
    hsi_dates = sorted(hsi_df["Date"].unique(), reverse=True)
    
    cd_h, ct_h = st.columns([2, 1])
    with cd_h:
        sel_hsi_date = st.selectbox("तारीख चुनें (Hang Seng Index):", hsi_dates, key="hsi_weighted_date")
    with ct_h:
        st.metric("वर्तमान समय (HKT)", now_hkt.strftime("%I:%M:%S %p"))
        
    res_h = run_weighted_engine(
        hsi_df[hsi_df["Date"] == sel_hsi_date],
        lock_time_str="15:50:00",
        mid_time_str="12:00:00",
        core_time_str="14:30:00",
        low_k=7,
        high_k=5
    )
    
    if res_h:
        if sel_hsi_date == now_hkt.date() and now_hkt.time() < time(15, 50):
            st.markdown('<div class="waiting-banner">⏳ लाइव मार्केट: ठीक 03:50 PM HKT पर वेटेड बास्केट लॉक होगी।</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="lock-banner">🔒 03:50 PM HKT पर लॉक की गई 15 बास्केट (Hang Seng ^HSI Weighted)</div>', unsafe_allow_html=True)
            
        st.subheader("🎯 आज की 15 बास्केट (Top 3 Weighted + 7 Low + 5 High)")
        badges_h = "".join([
            f"<span class='badge-hit'>🎯 .{x} (HIT)</span>" if (res_h['is_closed'] and x == res_h['actual_close_dec'])
            else f"<span class='badge-main'>.{x}</span>"
            for x in res_h['final_15']
        ])
        st.markdown(badges_h, unsafe_allow_html=True)
        
        c1_h, c2_h, c3_h = st.columns(3)
        with c1_h:
            st.markdown("**⭐ टॉप 3 वेटेड रिपीटर्स:**")
            st.markdown("".join([f"<span class='badge-top'>.{x} ({res_h['scores'][x]:.0f} pts)</span>" for x in res_h['top_3']]), unsafe_allow_html=True)
        with c2_h:
            st.markdown("**🟢 7 Lowest Barcode:**")
            st.markdown("".join([f"<span class='badge-low'>.{x}</span>" for x in res_h['lowest']]), unsafe_allow_html=True)
        with c3_h:
            st.markdown("**🔴 5 Highest Barcode:**")
            st.markdown("".join([f"<span class='badge-high'>.{x}</span>" for x in res_h['highest']]), unsafe_allow_html=True)
            
        st.divider()
        mh1, mh2, mh3 = st.columns(3)
        mh1.metric("03:50 PM लॉक भाव", f"{res_h['price_at_lock']:.2f}")
        if res_h["is_closed"]:
            mh2.metric("04:08 PM क्लोज भाव (^HSI Index)", f"{res_h['actual_close_price']:.2f} (.{res_h['actual_close_dec']})")
            mh3.metric("परिणाम", "✅ HIT" if res_h["is_hit"] else "❌ MISS", res_h["side"])
        else:
            mh2.metric("04:08 PM क्लोज भाव", "ऑक्शन में...")
            mh3.metric("परिणाम", "प्रतीक्षा में")
    else:
        st.warning("Hang Seng Index (^HSI) का डेटा लोड नहीं हो सका।")
