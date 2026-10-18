import streamlit as st
import yfinance as yf
import pandas as pd
from collections import Counter
from datetime import datetime, time
import pytz

st.set_page_config(page_title="Pre-Close Decimal Engine", page_icon="🎯", layout="wide")

IST = pytz.timezone("Asia/Kolkata")
HKT = pytz.timezone("Asia/Hong_Kong")

st.title("🎯 Pre-Close Decimal Engine (T-10 Min Lock)")
st.caption("BSE Sensex (8 Low + 7 High) & Hang Seng Index (9 Low + 6 High)")

@st.cache_data(ttl=10)
def fetch_clean_index(symbol, tz_str):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="60d", interval="2m")
    if df.empty or len(df) < 30:
        df = ticker.history(period="60d", interval="5m")
    if df.empty:
        df = ticker.history(period="60d", interval="1d")
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(tz_str)
    else:
        df.index = df.index.tz_convert(tz_str)
        
    df["Date"] = df.index.date
    df["Decimal"] = df["Close"].apply(lambda x: f"{float(x):.2f}".split(".")[1].zfill(2))
    
    df_daily = ticker.history(period="60d", interval="1d")
    daily_closes = {}
    if not df_daily.empty:
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)
        for d, row in df_daily.iterrows():
            daily_closes[d.date()] = (row["Close"], f"{float(row['Close']):.2f}".split(".")[1].zfill(2))
            
    return df, daily_closes

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
    
    repeaters = [k for k, v in core_counts.items() if v >= 2]
    uniques = [k for k, v in core_counts.items() if v == 1]
    confirmed = [k for k in uniques if all_day_counts.get(k, 0) >= 3]
    late_u = [k for k, v in late_counts.items() if v == 1]
    
    pool = list(dict.fromkeys(repeaters + confirmed + late_u))
    
    if len(pool) < 15:
        for d in df_pre["Decimal"].tolist()[::-1]:
            if d not in pool:
                pool.append(d)
            if len(pool) == 15:
                break
                
    pool_sorted = sorted(pool, key=lambda x: int(x))
    lowest = pool_sorted[:low_k]
    highest = pool_sorted[-high_k:]
    final_15 = list(dict.fromkeys(lowest + highest))
    
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

tab_bse, tab_hsi = st.tabs(["🏛️ BSE Sensex (8 Low + 7 High)", "🇭🇰 Hang Seng Index (9 Low + 6 High)"])

with tab_bse:
    now_ist = datetime.now(IST)
    bse_df, bse_daily = fetch_clean_index("^BSESN", "Asia/Kolkata")
    bse_dates = sorted(bse_df["Date"].unique(), reverse=True)
    sel_bse_date = st.selectbox("तारीख चुनें (BSE Sensex):", bse_dates, key="bse_box_final")
    
    res_b = run_engine(bse_df[bse_df["Date"] == sel_bse_date], bse_daily.get(sel_bse_date), "15:20:00", "14:00:00", "15:00:00", 8, 7)
    if res_b:
        st.subheader("🎯 15 उम्मीदवारों की मुख्य बास्केट (BSE Sensex)")
        st.write(" ".join([f"` .{x} `" if x != res_b['actual_dec'] else f"**:green[🎯 .{x} (HIT)]**" for x in res_b['final_15']]))
        c1, c2, c3 = st.columns(3)
        c1.metric("03:20 PM लॉक भाव", f"{res_b['price_at_lock']:.2f}")
        c2.metric("03:30 PM आधिकारिक क्लोज", f"{res_b['actual_price']:.2f} (.{res_b['actual_dec']})")
        c3.metric("परिणाम", "✅ HIT" if res_b["is_hit"] else "❌ MISS", res_b["side"])

with tab_hsi:
    now_hkt = datetime.now(HKT)
    hsi_df, hsi_daily = fetch_clean_index("^HSI", "Asia/Hong_Kong")
    hsi_dates = sorted(hsi_df["Date"].unique(), reverse=True)
    sel_hsi_date = st.selectbox("तारीख चुनें (Hang Seng Index):", hsi_dates, key="hsi_box_final")
    
    res_h = run_engine(hsi_df[hsi_df["Date"] == sel_hsi_date], hsi_daily.get(sel_hsi_date), "15:50:00", "14:30:00", "15:30:00", 9, 6)
    if res_h:
        st.subheader("🎯 15 उम्मीदवारों की मुख्य बास्केट (Hang Seng ^HSI)")
        st.write(" ".join([f"` .{x} `" if x != res_h['actual_dec'] else f"**:green[🎯 .{x} (HIT)]**" for x in res_h['final_15']]))
        c1, c2, c3 = st.columns(3)
        c1.metric("03:50 PM लॉक भाव (^HSI)", f"{res_h['price_at_lock']:.2f}")
        c2.metric("04:08 PM आधिकारिक क्लोज (^HSI)", f"{res_h['actual_price']:.2f} (.{res_h['actual_dec']})")
        c3.metric("परिणाम", "✅ HIT" if res_h["is_hit"] else "❌ MISS", res_h["side"])
