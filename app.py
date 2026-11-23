import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

st.set_page_config(page_title="Nifty & BTST Agent", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# ULTRA-TIGHT SINGLE-VIEWPORT CSS
# ==========================================
st.markdown("""
<style>
    .block-container { padding: 0.35rem 0.7rem 0.2rem 0.7rem !important; max-width: 100% !important; }
    header[data-testid="stHeader"], footer, #MainMenu { display: none !important; }
    div[data-testid="stVerticalBlock"] > div { gap: 0.22rem !important; }
    div[data-testid="stMetric"] {
        background: #0e131a; border: 1px solid #26303d;
        padding: 4px 8px !important; border-radius: 5px;
    }
    div[data-testid="stMetricLabel"] { font-size: 0.66rem !important; line-height: 1.1 !important; }
    div[data-testid="stMetricValue"] { font-size: 0.92rem !important; line-height: 1.15 !important; }
    div[data-testid="stMetricDelta"] { font-size: 0.63rem !important; line-height: 1.1 !important; }
    .hdr-bar { font-size: 0.85rem; font-weight: 700; color: #f0f4f8; margin: 0; padding: 2px 0; }
    .sec-hdr { font-size: 0.78rem; font-weight: 700; color: #93c5fd; margin: 2px 0; }
</style>
""", unsafe_allow_html=True)

IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)

UNIVERSE = [
    "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "KPITTECH.NS", "TATAELXSI.NS",
    "POLYCAB.NS", "KEI.NS", "DIXON.NS", "KAYNES.NS", "AMBER.NS",
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "AUBANK.NS", "BANDHANBNK.NS", "CANBK.NS",
    "CUMMINSIND.NS", "BHARATFORG.NS", "ASTRAL.NS", "SUPREMEIND.NS", "APLAPOLLO.NS",
    "MAXHEALTH.NS", "FORTIS.NS", "LALPATHLAB.NS", "SYNGENE.NS", "LAURUSLABS.NS",
    "OBEROIRLTY.NS", "PRESTIGE.NS", "PHOENIXLTD.NS", "BRIGADE.NS", "GODREJPROP.NS",
    "INDIANB.NS", "UNIONBANK.NS", "MAHABANK.NS", "EXIDEIND.NS", "ARE&M.NS",
    "CROMPTON.NS", "VOLTAS.NS", "BLUESTARCO.NS", "WHIRLPOOL.NS", "HAVELLS.NS"
]

@st.cache_data(ttl=300)
def load_indices():
    data = {}
    for t in ["^NSEI", "^CNXMIDCAP", "^CNXSC"]:
        df = yf.download(t, period="10y" if t == "^NSEI" else "1mo", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna().copy()
        df["Pct"] = df["Close"].pct_change() * 100
        df["Green"] = df["Pct"] > 0
        df["Red"] = df["Pct"] < 0
        data[t] = df
    return data

@st.cache_data(ttl=900)
def run_sys3_btst(tickers):
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=365 * 5)
    raw_daily = yf.download(tickers, start=start_dt.strftime("%Y-%m-%d"),
                            end=end_dt.strftime("%Y-%m-%d"), group_by="ticker", progress=False)
    raw_5m = yf.download(tickers, period="60d", interval="5m", group_by="ticker", progress=False)

    all_trades, live_candidates = [], []
    MEDIAN_TARGET = 0.0055

    for sym in tickers:
        if sym not in raw_daily or raw_daily[sym].empty:
            continue
        df = raw_daily[sym].dropna().copy()
        if len(df) < 50:
            continue

        df["Pct"] = df["Close"].pct_change()
        df["Green"] = df["Pct"] > 0
        df["Vol_Avg20"] = df["Volume"].rolling(20).mean()
        df["VolX"] = df["Volume"] / df["Vol_Avg20"]
        df["Turnover_Cr"] = (df["Close"] * df["Volume"]) / 1e7

        streak, cnt = [], 0
        for g in df["Green"]:
            cnt = cnt + 1 if g else 0
            streak.append(cnt)
        df["Streak"] = streak

        latest = df.iloc[-1]
        if latest["Streak"] >= 3 and latest["VolX"] >= 1.2 and latest["Turnover_Cr"] >= 15.0:
            live_candidates.append({
                "Stock": sym.replace(".NS", ""),
                "Day": f"G{int(latest['Streak'])}",
                "3:20 Px": round(latest["Close"], 1),
                "Chg%": f"+{round(latest['Pct']*100, 2)}%",
                "VolX": f"{round(latest['VolX'], 1)}x",
                "Score": round(latest["VolX"] * latest["Pct"] * 100, 2)
            })

        exact_320, exact_920 = {}, {}
        if sym in raw_5m and not raw_5m[sym].empty:
            df5 = raw_5m[sym].dropna().copy()
            if df5.index.tz is not None:
                df5.index = df5.index.tz_convert("Asia/Kolkata")
            for ts, r5 in df5.iterrows():
                d_s, t_s = ts.strftime("%Y-%m-%d"), ts.strftime("%H:%M")
                if t_s == "15:20":
                    exact_320[d_s] = r5["Close"]
                elif t_s == "09:20":
                    exact_920[d_s] = r5["Close"]

        df["Next_Date"] = df.index.to_series().shift(-1).dt.strftime("%Y-%m-%d")
        df["Next_Open"] = df["Open"].shift(-1)
        df["Next_High"] = df["High"].shift(-1)
        df["Score"] = df["VolX"] * (df["Pct"] * 100)

        cond = (df["Streak"] >= 3) & (df["VolX"] >= 1.2) & (df["Turnover_Cr"] >= 15.0) & df["Next_Open"].notna()
        for dt, row in df[cond].iterrows():
            d_s, nd_s = dt.strftime("%Y-%m-%d"), row["Next_Date"]
            entry_px = exact_320.get(d_s, row["Close"])
            if nd_s in exact_920:
                exit_px = exact_920[nd_s]
            else:
                tgt = entry_px * (1 + MEDIAN_TARGET)
                exit_px = row["Next_Open"] if row["Next_Open"] >= tgt else (tgt if row["Next_High"] >= tgt else row["Next_Open"])
            ret_pct = ((exit_px - entry_px) / entry_px) * 100
            all_trades.append({
                "Date": d_s[5:], "Symbol": sym.replace(".NS", ""), "Day": f"G{int(row['Streak'])}",
                "In": round(entry_px, 1), "Out": round(exit_px, 1), "Ret%": round(ret_pct, 2), "Score": row["Score"]
            })

    trades_df = pd.DataFrame(all_trades)
    live_df = pd.DataFrame(live_candidates)
    if not live_df.empty:
        live_df = live_df.sort_values("Score", ascending=False).head(7).drop(columns=["Score"])
    if trades_df.empty:
        return None, pd.DataFrame(), live_df

    trades_df = trades_df.sort_values(["Date", "Score"], ascending=[True, False])
    top7 = trades_df.groupby("Date").head(7).reset_index(drop=True)
    return {
        "win_rate": round((top7["Ret %"] > 0).mean() * 100, 1),
        "median_ret": round(top7["Ret %"].median(), 2),
        "total_trades": len(top7)
    }, top7, live_df

idx = load_indices()
nifty = idx["^NSEI"]
spot = round(nifty["Close"].iloc[-1], 2)
atm = int(round(spot / 50.0) * 50)

# ==========================================
# ROW 1: COMPACT TITLE + 3 INDEX OHLC STRIP
# ==========================================
c_title, c_n50, c_mid, c_sml = st.columns([1.8, 1, 1, 1])
with c_title:
    st.markdown(f"<div class='hdr-bar'>📊 NIFTY & BTST AGENT | {now_ist.strftime('%d-%b %H:%M IST')}</div>", unsafe_allow_html=True)
    st.caption("3:15 Check • 3:20 Exec • 9:15–9:20 Exit")

for col, (lbl, sym) in zip([c_n50, c_mid, c_sml], [("NIFTY 50", "^NSEI"), ("MIDCAP 100", "^CNXMIDCAP"), ("SMALLCAP 100", "^CNXSC")]):
    d = idx[sym].iloc[-1]
    col.metric(f"{lbl} ({d['Pct']:+.2f}%)", f"{d['Close']:,.1f}", f"O:{d['Open']:,.0f} H:{d['High']:,.0f} L:{d['Low']:,.0f}")

# ==========================================
# ROW 2: HORIZONTAL 8-DAY NIFTY STRIP (LATEST ON LEFT)
# ==========================================
recent_n = nifty.tail(8).iloc[::-1]
horiz_nifty = pd.DataFrame(
    [
        [f"{r['Close']:,.1f}" for _, r in recent_n.iterrows()],
        [f"{r['Pct']:+.2f}%" for _, r in recent_n.iterrows()],
        ["🟢 G" if r["Green"] else "🔴 R" for _, r in recent_n.iterrows()]
    ],
    index=["Close", "Chg%", "Stat"],
    columns=[d.strftime("%d-%b") for d in recent_n.index]
)
st.dataframe(horiz_nifty, use_container_width=True, height=112)

# ==========================================
# ROW 3: ALL 3 ENCODED SYSTEMS SIDE-BY-SIDE
# ==========================================
s1_col, s2_col, s3_col = st.columns(3)

with s1_col:
    g3 = nifty["Green"].iloc[-1] and nifty["Green"].iloc[-2] and nifty["Green"].iloc[-3]
    r3 = nifty["Red"].iloc[-1] and nifty["Red"].iloc[-2] and nifty["Red"].iloc[-3]
    s1_bull = nifty["Green"] & nifty["Green"].shift(1) & nifty["Green"].shift(2)
    s1_bear = nifty["Red"] & nifty["Red"].shift(1) & nifty["Red"].shift(2)
    next_open_ret = ((nifty["Open"].shift(-1) - nifty["Close"]) / nifty["Close"]) * 100
    s1_wr = round(((next_open_ret[s1_bull].dropna() > 0).mean() + (next_open_ret[s1_bear].dropna() < 0).mean()) * 50, 1)

    st.markdown(f"<div class='sec-hdr'>1️⃣ SYS-1: 3D Debit Spread (WR: {s1_wr}%)</div>", unsafe_allow_html=True)
    if g3:
        st.metric("ACTIVE: 3G BULL", f"BUY {atm} CE | SELL {atm+150} CE", "3:20 PM -> 9:15/9:20 AM (+0.15%)")
    elif r3:
        st.metric("ACTIVE: 3R BEAR", f"BUY {atm} PE | SELL {atm-150} PE", "3:20 PM -> 9:15/9:20 AM (+0.15%)")
    else:
        st.metric("STANDBY (Needs 3G/3R)", f"Spot {spot:,.1f} | ATM {atm}", "3:20 PM Entry -> 9:20 AM Force-Cut")

with s2_col:
    s3_ret = ((nifty["Close"].iloc[-1] - nifty["Close"].iloc[-4]) / nifty["Close"].iloc[-4]) * 100
    s5_ret = ((nifty["Close"].iloc[-1] - nifty["Close"].iloc[-6]) / nifty["Close"].iloc[-6]) * 100
    flip = (nifty["Green"].iloc[-1] != nifty["Green"].iloc[-2])
    ic1 = (abs(s3_ret) < 1.0) and (abs(s5_ret) < 1.5) and flip
    ic2 = ((s3_ret * s5_ret) < 0) and flip and not ic1

    st.markdown("<div class='sec-hdr'>2️⃣ SYS-2: 5D Iron Condor (IC1:85.5% | IC2:83%)</div>", unsafe_allow_html=True)
    if ic1 or ic2:
        tag = "IC-1 ACTIVE" if ic1 else "IC-2 ACTIVE"
        st.metric(f"{tag} (S3:{s3_ret:+.2f}% S5:{s5_ret:+.2f}%)", f"Sell {atm-750}PE/{atm+750}CE", f"Hedge {atm-1000}PE/{atm+1000}CE | 55% Tgt")
    else:
        st.metric(f"STANDBY (Flip:{'Y' if flip else 'N'})", f"S3: {s3_ret:+.2f}% | S5: {s5_ret:+.2f}%", "±750 Corridor | Tgt 55% | Max 5D")

btst_stats, btst_ledger, btst_live = run_sys3_btst(UNIVERSE)
with s3_col:
    if btst_stats:
    if btst_stats:
        st.markdown(f"<div class='sec-hdr'>3️⃣ SYS-3: Cash BTST (WR: {btst_stats['win_rate']}%)</div>", unsafe_allow_html=True)
        st.metric(f"Day 3+ Green ({btst_stats['total_trades']} Trades)", f"Median: +{btst_stats['median_ret']}% / Trade", "3:20 PM -> 9:20 AM / +0.55% Tgt")
    else:
        st.markdown("<div class='sec-hdr'>3️⃣ SYS-3: Cash BTST</div>", unsafe_allow_html=True)
        st.metric("STANDBY", "No Data", "3:20 PM -> 9:20 AM")

# ==========================================
# ROW 4: COMPACT TOP-7 LIVE & RECENT BACKTEST TABLES
# ==========================================
t1, t2 = st.columns([1, 1.35])
with t1:
    st.markdown("<div class='sec-hdr'>🎯 Live 3:20 PM Top-7 BTST (Day 3+ Green)</div>", unsafe_allow_html=True)
    if not btst_live.empty:
        st.dataframe(btst_live, use_container_width=True, hide_index=True, height=135)
    else:
        st.caption("No stocks currently meet Day 3+ Green + 1.2x Vol + >₹15 Cr.")

with t2:
    st.markdown("<div class='sec-hdr'>📜 SYS-3 Backtest Ledger (3:20 PM -> 9:20 AM / Med %)</div>", unsafe_allow_html=True)
    if not btst_ledger.empty:
        st.dataframe(btst_ledger.tail(6).iloc[::-1].drop(columns=["Score"]), use_container_width=True, hide_index=True, height=135)
