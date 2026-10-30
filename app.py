"""
BSE SENSEX CLOSING DECIMAL ENGINE - 100% PERSISTENT ACROSS BROWSER RELOADS
Multi Cut-off Windows: 03:15 PM, 03:20 PM, 03:25 PM IST
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime

st.set_page_config(
    page_title="BSE Sensex Cut-Off Decimal Engine (Locked)",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded"
)

IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)
today_str = now_ist.strftime("%Y-%m-%d")

SYMBOL = "^BSESN"

CUTOFFS = {
    "Cut-off 1 (03:15 PM)": {
        "cutoff_hour": 15,
        "cutoff_min": 15,
        "cutoff_label": "03:15 PM IST"
    },
    "Cut-off 2 (03:20 PM)": {
        "cutoff_hour": 15,
        "cutoff_min": 20,
        "cutoff_label": "03:20 PM IST"
    },
    "Cut-off 3 (03:25 PM)": {
        "cutoff_hour": 15,
        "cutoff_min": 25,
        "cutoff_label": "03:25 PM IST"
    }
}

def extract_dec(price: float) -> int:
    return int(f"{price:.2f}".split(".")[1])

def get_band(center_dec: int, half_size: int = 7) -> set:
    return {(center_dec + k) % 100 for k in range(-half_size, half_size + 1)}

# कट-ऑफ पार होने के बाद सर्वर मेमोरी में स्थायी लॉक (ttl=None)
@st.cache_data(ttl=None, show_spinner=False)
def get_locked_bse_data(symbol: str, date_str: str, cut_h: int, cut_m: int):
    t = yf.Ticker(symbol)
    df = t.history(period="5d", interval="5m")
    if df.empty:
        return None

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(IST)
    else:
        df.index = df.index.tz_convert(IST)

    cutoff_limit = now_ist.replace(hour=cut_h, minute=cut_m, second=0, microsecond=0)
    filtered = df[df.index <= cutoff_limit]
    if filtered.empty:
        filtered = df

    target_row = filtered.iloc[-1]
    price = float(target_row["Close"])
    bar_time = filtered.index[-1].strftime("%I:%M %p IST")

    # इंडिकेटिव VWAP (कट-ऑफ से पहले की 15 बार्स)
    win = filtered.tail(15)
    typ_p = (win["High"] + win["Low"] + win["Close"]) / 3.0
    vol = win["Volume"]
    vwap = (typ_p * vol).sum() / vol.sum() if vol.sum() > 0 else typ_p.mean()

    dec_p = extract_dec(price)
    dec_v = extract_dec(vwap)
    band_p = get_band(dec_p, 7)
    band_v = get_band(dec_v, 7)

    return {
        "price": price,
        "dec_p": dec_p,
        "vwap": vwap,
        "dec_v": dec_v,
        "combined": sorted(list(band_p.union(band_v))),
        "prime": sorted(list(band_p.intersection(band_v))),
        "locked_bar_time": bar_time
    }

# कट-ऑफ से पहले लाइव ट्रैकिंग (15 सेकंड कैश)
@st.cache_data(ttl=15, show_spinner=False)
def get_live_bse_data(symbol: str):
    t = yf.Ticker(symbol)
    df = t.history(period="2d", interval="5m")
    if df.empty:
        return None

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(IST)
    else:
        df.index = df.index.tz_convert(IST)

    target_row = df.iloc[-1]
    price = float(target_row["Close"])
    bar_time = df.index[-1].strftime("%I:%M %p IST")

    win = df.tail(15)
    typ_p = (win["High"] + win["Low"] + win["Close"]) / 3.0
    vol = win["Volume"]
    vwap = (typ_p * vol).sum() / vol.sum() if vol.sum() > 0 else typ_p.mean()

    dec_p = extract_dec(price)
    dec_v = extract_dec(vwap)
    band_p = get_band(dec_p, 7)
    band_v = get_band(dec_v, 7)

    return {
        "price": price,
        "dec_p": dec_p,
        "vwap": vwap,
        "dec_v": dec_v,
        "combined": sorted(list(band_p.union(band_v))),
        "prime": sorted(list(band_p.intersection(band_v))),
        "locked_bar_time": bar_time
    }

st.title("🔒 BSE Sensex कट-ऑफ परमानेंट लॉक इंजन")
st.caption("कट-ऑफ 1: 03:15 PM • कट-ऑफ 2: 03:20 PM • कट-ऑफ 3: 03:25 PM IST")

cols = st.columns(3)

for idx_i, (c_name, meta) in enumerate(CUTOFFS.items()):
    with cols[idx_i]:
        st.subheader(c_name)
        st.caption(f"कट-ऑफ विंडो: **{meta['cutoff_label']}**")

        cut_h = meta["cutoff_hour"]
        cut_m = meta["cutoff_min"]
        is_locked = (now_ist.hour > cut_h) or (now_ist.hour == cut_h and now_ist.minute >= cut_m)

        if is_locked:
            # सर्वर के परमानेंट मेमोरी कैश से डेटा आएगा (रीलोड पर कभी नहीं बदलेगा)
            res = get_locked_bse_data(SYMBOL, today_str, cut_h, cut_m)
            st.success(f"🔒 **डेटा स्थायी रूप से लॉक है ({meta['cutoff_label']})**")
        else:
            # कट-ऑफ से पहले लाइव टिक चलेगा
            res = get_live_bse_data(SYMBOL)
            st.warning(f"⏳ लाइव चल रहा है (कट-ऑफ {meta['cutoff_label']} पर लॉक होगा)")

        if not res:
            st.error("डेटा लोड नहीं हो सका।")
            continue

        st.metric(
            label="BSE Sensex भाव (INR)",
            value=f"{res['price']:,.2f}",
            delta=f"दशमलव: .{res['dec_p']:02d}"
        )
        st.write(f"• इंडिकेटिव VWAP: **.{res['dec_v']:02d}** ({res['vwap']:,.2f})")
        st.caption(f"🔒 लॉक्ड टिक समय: `{res['locked_bar_time']}`")

        st.markdown(f"**🔥 प्राइम कोर ({len(res['prime'])} nos):**")
        if res["prime"]:
            st.markdown(" ".join([f"` .{x:02d} `" for x in res["prime"]]))
        else:
            st.caption("कोई प्राइम ओवरलैप नहीं")

        st.markdown(f"**📋 पूर्ण बास्केट ({len(res['combined'])} नंबर्स):**")
        st.markdown(" ".join([
            f"<span style='background-color:#1e293b;color:#38bdf8;padding:4px 8px;border-radius:4px;font-weight:bold;margin:2px;display:inline-block;'>.{x:02d}</span>"
            for x in res["combined"]
        ]), unsafe_allow_html=True)
