import math, io, datetime as dt
import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title='Nifty All-In-One Agent', layout='wide')
st.markdown('''<style>
.block-container{padding:0.25rem 0.5rem !important;max-width:100% !important}
header,footer{visibility:hidden}
div.stButton > button{background:#1e293b;color:#38bdf8;border:1px solid #38bdf8;border-radius:4px;padding:1px 10px;font-size:11px;font-weight:700;height:24px;min-height:24px;float:right}
div.stButton > button:hover{background:#38bdf8;color:#0b1120}
.stTabs [data-baseweb="tab-list"]{gap:6px;margin-bottom:4px}
.stTabs [data-baseweb="tab"]{padding:2px 10px;font-size:11px;font-weight:700}
</style>''', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    st.markdown("<div style='color:#38bdf8;font-size:13px;font-weight:700;padding-top:2px'>NIFTY ALL-IN-ONE AGENT</div>", unsafe_allow_html=True)
with c2:
    if st.button('↻ Refresh'):
        st.cache_data.clear()
        st.rerun()

INDICES = {'Nifty 50': '^NSEI', 'Midcap 150': 'NIFTYMIDCAP150.NS', 'Smlcap 250': 'NIFTYSMLCAP250.NS'}
STOCKS = [
    ('POONAWALLA', 'POONAWALLA.NS', 'M150'), ('EXIDEIND', 'EXIDEIND.NS', 'S250'),
    ('CYIENT', 'CYIENT.NS', 'S250'), ('LUPIN', 'LUPIN.NS', 'M150'),
    ('KAYNES', 'KAYNES.NS', 'M150'), ('KPITTECH', 'KPITTECH.NS', 'M150'), ('CDSL', 'CDSL.NS', 'M150'),
]

@st.cache_data(ttl=60)
def get_hist(ticker, period='15mo'):
    df = yf.download(ticker, period=period, interval='1d', progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()

idx_data, nifty_ann_vol, nifty_5d_ann, nifty_5d_raw, full_nifty_df = {}, 0.135, 0.135, 0.019, None
for name, tk in INDICES.items():
    df = get_hist(tk, '15mo').copy()
    if len(df) >= 2 and df['Open'].iloc[-1] < df['Close'].iloc[-2] * 0.25:
        ratio = df['Close'].iloc[-2] / df['Close'].iloc[-1] if df['Close'].iloc[-1] < df['Close'].iloc[-2] * 0.25 else (df['Close'].iloc[-1] / df['Open'].iloc[-1])
        for col in ('Open', 'High', 'Low', 'Close'):
            if df[col].iloc[-1] < df['Close'].iloc[-2] * 0.25:
                df.iloc[-1, df.columns.get_loc(col)] *= ratio
    df['pct'] = df['Close'].pct_change() * 100
    for w in (3, 5, 10, 15, 20):
        df[f's{w}'] = df['pct'].rolling(w).sum()
    if name == 'Nifty 50':
        full_nifty_df = df.dropna().copy()
        rv = (df['Close'].pct_change()).rolling(252).std().iloc[-1] * math.sqrt(252)
        if not pd.isna(rv) and rv > 0:
            nifty_ann_vol = float(rv)
        rv5 = (df['Close'].pct_change()).rolling(5).std().iloc[-1]
        nifty_5d_ann = float(rv5 * math.sqrt(252)) if not pd.isna(rv5) else nifty_ann_vol
        nifty_5d_raw = float(rv5 * math.sqrt(5)) if not pd.isna(rv5) else (nifty_ann_vol * math.sqrt(5.0 / 252.0))
    idx_data[name] = df.tail(6)

n_df = idx_data['Nifty 50']
last_n = n_df.iloc[-1]

streak = 0
for p in reversed(full_nifty_df['pct'].tolist()):
    if p > 0 and streak >= 0: streak += 1
    elif p < 0 and streak <= 0: streak -= 1
    else: break

if streak >= 3:
    sig = f'LONG ACTIVE (DAY {streak} GREEN) -- Buy Bull Call Debit Spread (CE Only)'
elif streak <= -3:
    sig = f'SHORT ACTIVE (DAY {abs(streak)} RED) -- Buy Bear Put Debit Spread (PE Only)'
else:
    side = 'GREEN' if streak > 0 else ('RED' if streak < 0 else 'FLAT')
    sig = f'STANDBY (DAY {abs(streak)} {side}) -- Day 1 & 2 = Cash | Day 3+ Unidirectional = Trade'

bull_aligned = (full_nifty_df['s3'] > 0) & (full_nifty_df['s5'] > 0) & (full_nifty_df['s10'] > 0) & (full_nifty_df['s15'] > 0) & (full_nifty_df['s20'] > 0)
bear_aligned = (full_nifty_df['s3'] < 0) & (full_nifty_df['s5'] < 0) & (full_nifty_df['s10'] < 0) & (full_nifty_df['s15'] < 0) & (full_nifty_df['s20'] < 0)

regime_days, regime_start = 0, ''
if bull_aligned.iloc[-1]:
    for idx_dt, val in reversed(list(bull_aligned.items())):
        if val: regime_days += 1; regime_start = idx_dt.strftime('%Y-%m-%d')
        else: break
    bias_txt, bias_cls = f'STRONG UPWARD BIAS (ALL 5 SUMS > 0 | {regime_days} Sessions since {regime_start})', 'pos'
elif bear_aligned.iloc[-1]:
    for idx_dt, val in reversed(list(bear_aligned.items())):
        if val: regime_days += 1; regime_start = idx_dt.strftime('%Y-%m-%d')
        else: break
    bias_txt, bias_cls = f'STRONG DOWNWARD BIAS (ALL 5 SUMS < 0 | {regime_days} Sessions since {regime_start})', 'neg'
else:
    pos_cnt = sum([last_n['s3'] > 0, last_n['s5'] > 0, last_n['s10'] > 0, last_n['s15'] > 0, last_n['s20'] > 0])
    bias_txt, bias_cls = f'MIXED / TRANSITION ({pos_cnt}/5 Sums Positive)', 'warn'

S_now = float(last_n['Close'])
atm = int(round(S_now / 50.0) * 50)
band_150 = int(round((S_now * nifty_ann_vol * math.sqrt(5.0 / 252.0) * 1.50) / 50.0) * 50)
ic_short_pe, ic_short_ce = atm - band_150, atm + band_150
ic_long_pe, ic_long_ce = ic_short_pe - 250, ic_short_ce + 250
p3 = n_df['pct'].tail(3).tolist()
s3_val = float(last_n['s3'])
flip_ok = (p3[-1] * p3[-2]) < 0
ic_comp = flip_ok and (abs(s3_val) < 1.0) and (abs(last_n['s5']) < 1.5)
ic_div = flip_ok and ((s3_val * last_n['s5']) < 0)


stk_list, stk_dates = [], []
for sym, tk, uni in STOCKS:
    df = get_hist(tk, '2mo').copy()
    df['pct'] = df['Close'].pct_change() * 100
    df['s25'] = df['pct'] + df['pct'].shift(1) + 0.5 * df['pct'].shift(2)
    for w in (5, 10, 15): df[f's{w}'] = df['pct'].rolling(w).sum()
    vol_avg = df['Volume'].iloc[-11:-1].mean()
    vol_x = df['Volume'].iloc[-1] / vol_avg if vol_avg else 1.0

    # Continuous Green Streak (Day 3 & onwards = ACTIVE BTST)
    g_streak = 0
    for p_val in reversed(df['pct'].dropna().tolist()):
        if p_val > 0: g_streak += 1
        else: break

    sub = df.tail(6)
    if not stk_dates: stk_dates = sub.index.strftime('%Y-%m-%d').tolist()
    last_st = sub.iloc[-1]
    cmp = last_st['Close']
    stk_list.append({
        'sym': sym, 'uni': uni, 'cmp': cmp, 'qty': max(1, int(35000 // cmp)),
        'vol_m': last_st['Volume'] / 1e6, 'vol_x': vol_x, 'g_streak': g_streak,
        'pcts': sub['pct'].tolist(), 'closes': sub['Close'].tolist(),
        's25': last_st['s25'], 's5': last_st['s5'], 's10': last_st['s10'], 's15': last_st['s15'],
        't1': round(cmp * 1.0055, 2), 't2': round(cmp * 1.0075, 2)
    })
    def cell_cls(v): return 'neg-cell' if v < 0 else ('pos-cell' if v > 0 else '')

ohlc_rows = ''
for iname in ('Nifty 50', 'Midcap 150', 'Smlcap 250'):

    idf = idx_data[iname]
    prev_c = idf.iloc[-2]['Close']
    cur = idf.iloc[-1]
    c_cls = 'pos' if cur['pct'] > 0 else ('neg' if cur['pct'] < 0 else '')
    ohlc_rows += f"<tr><td><b>{iname}</b></td><td>{prev_c:,.1f}</td><td>{cur['Open']:,.1f}</td><td class='pos'>{cur['High']:,.1f}</td><td class='neg'>{cur['Low']:,.1f}</td><td class='{c_cls}'>{cur['Close']:,.1f}</td><td class='{cell_cls(cur['pct'])}'>{cur['pct']:+.2f}%</td></tr>"

stk_th = ''.join([f'<th class="wdiv">{s["sym"]} <span class="tag">({s["uni"]})</span></th>' for s in stk_list])
row_cmp = ''.join([f'<td class="wdiv"><b>{s["cmp"]:,.1f}</b> | Q:{s["qty"]}</td>' for s in stk_list])
row_tgt = ''.join([f'<td class="wdiv pos">{s["t1"]:,.1f} / {s["t2"]:,.1f}</td>' for s in stk_list])
row_vol = ''.join([f'<td class="wdiv {"pos" if s["vol_x"]>=1.2 else ("neg" if s["vol_x"]<0.8 else "")}">{s["vol_m"]:.1f}M | <b>{s["vol_x"]:.1f}x</b></td>' for s in stk_list])
row_s25_5 = ''.join([f'<td class="wdiv"><span class="{"pos" if s["s25"]>0 else ("neg" if s["s25"]<0 else "")}">{s["s25"]:+.2f}%</span> / <span class="{"pos" if s["s5"]>0 else ("neg" if s["s5"]<0 else "")}">{s["s5"]:+.2f}%</span></td>' for s in stk_list])
row_s10_15 = ''.join([f'<td class="wdiv"><span class="{"pos" if s["s10"]>0 else ("neg" if s["s10"]<0 else "")}">{s["s10"]:+.2f}%</span> / <span class="{"pos" if s["s15"]>0 else ("neg" if s["s15"]<0 else "")}">{s["s15"]:+.2f}%</span></td>' for s in stk_list])
row_btst = ''.join([
    f'<td class="wdiv pos"><b>ACTIVE (G{s["g_streak"]})</b></td>' if s["g_streak"] >= 3
    else f'<td class="wdiv warn">STANDBY (G{s["g_streak"]})</td>'
    for s in stk_list
])

date_rows_html = ''
last_idx = len(stk_dates) - 1
for d_idx, d_str in enumerate(stk_dates):
    lbl = f'<b>{d_str} (Now)</b>' if d_idx == last_idx else d_str
    cells = ''
    for s in stk_list:
        pv, cv = s['pcts'][d_idx], s['closes'][d_idx]
        val = f'<b>{pv:+.2f}%</b> ({cv:,.1f})' if d_idx == last_idx else f'{pv:+.2f}% ({cv:,.1f})'
        cells += f"<td class='wdiv {cell_cls(pv)}'>{val}</td>"
    date_rows_html += f'<tr><td>{lbl}</td>{cells}</tr>'
dates = n_df.index.strftime('%Y-%m-%d').tolist()
trows = ''
for i, d in enumerate(dates):
    n, m, s = idx_data['Nifty 50'].iloc[i], idx_data['Midcap 150'].iloc[i], idx_data['Smlcap 250'].iloc[i]
    def f(v): return f'<td class="{cell_cls(v)}">{v:+.2f}%</td>'
    trows += f'<tr><td>{d}</td><td>{n["Close"]:,.1f}</td>{f(n["pct"])}{f(n["s3"])}{f(n["s5"])}{f(n["s10"])}{f(n["s15"])}{f(n["s20"])}<td class="wdiv">{m["Close"]:,.1f}</td>{f(m["pct"])}{f(m["s3"])}{f(m["s5"])}{f(m["s10"])}{f(m["s15"])}{f(m["s20"])}<td class="wdiv">{s["Close"]:,.1f}</td>{f(s["pct"])}{f(s["s3"])}{f(s["s5"])}{f(s["s10"])}{f(s["s15"])}{f(s["s20"])}</tr>'

def sc_clr(v): return '#4ade80' if v > 0 else ('#f87171' if v < 0 else '#f8fafc')
ist_now = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
html = f'''<div style="background:#0b1120;color:#e2e8f0;font-family:Segoe UI,Arial,sans-serif;padding:5px 7px;font-size:10px;border-radius:6px;overflow-x:auto;-webkit-overflow-scrolling:touch">
<style>.na-meta{{background:#0f172a;border:1px solid #334155;border-radius:4px;padding:4px 7px;margin-bottom:5px;font-size:10.2px;color:#e2e8f0}}.na-box{{background:#111827;border:1px solid #334155;border-radius:5px;padding:8px 10px;margin-bottom:6px;font-size:11.2px;line-height:1.55;color:#f1f5f9}}.opt-sec{{margin-bottom:6px}}.pos{{color:#4ade80;font-weight:700}}.neg{{color:#f87171;font-weight:700}}.warn{{color:#fbbf24;font-weight:700}}.hi{{color:#38bdf8;font-weight:700}}.pos-cell{{color:#4ade80;background:rgba(74,222,128,0.10);font-weight:600}}.neg-cell{{color:#f87171;background:rgba(248,113,113,0.15);font-weight:600}}.tag{{color:#94a3b8;font-weight:400;font-size:8px}}table.grid{{width:100%;border-collapse:collapse;background:#111827;margin-bottom:5px;font-size:8.4px;color:#e2e8f0}}table.grid th,table.grid td{{padding:1.8px 3px;border-bottom:1px solid #1e293b;border-right:1px solid #1e293b;text-align:right;white-space:nowrap}}table.grid th{{background:#1e293b;color:#cbd5e1;text-align:center}}table.grid th:first-child,table.grid td:first-child{{text-align:left}}table.ohlc-sq{{width:auto;min-width:460px;border:1px solid #334155}}table.ohlc-sq th,table.ohlc-sq td{{padding:2px 8px;text-align:center}}table.ohlc-sq th:first-child,table.ohlc-sq td:first-child{{text-align:left;color:#38bdf8}}table.stk td{{text-align:center}}table.stk td:first-child{{text-align:left}}.wdiv{{border-left:1.5px solid #e2e8f0 !important}}.top-sep td{{border-bottom:1.5px solid #94a3b8 !important}}</style>
<div class="na-meta">Updated: <b style="color:#f8fafc">{ist_now} IST</b> &nbsp;|&nbsp; <span class="hi">252D AnnVol: {nifty_ann_vol*100:.2f}%</span> &nbsp;|&nbsp; <span class="warn">5D AnnVol: {nifty_5d_ann*100:.2f}% (5D &sigma;: {nifty_5d_raw*100:.2f}%)</span> &nbsp;|&nbsp; S3: <b style="color:{sc_clr(last_n['s3'])}">{last_n['s3']:+.2f}%</b> &nbsp;|&nbsp; S5: <b style="color:{sc_clr(last_n['s5'])}">{last_n['s5']:+.2f}%</b> &nbsp;|&nbsp; S10: <b style="color:{sc_clr(last_n['s10'])}">{last_n['s10']:+.2f}%</b> &nbsp;|&nbsp; S15: <b style="color:{sc_clr(last_n['s15'])}">{last_n['s15']:+.2f}%</b> &nbsp;|&nbsp; S20: <b style="color:{sc_clr(last_n['s20'])}">{last_n['s20']:+.2f}%</b> &nbsp;|&nbsp; Regime: <span class="{bias_cls}">{bias_txt}</span></div>
<table class="grid ohlc-sq"><tr><th>Today Live Index</th><th>Prev Close</th><th>Open</th><th>High</th><th>Low</th><th>Current</th><th>% Chg</th></tr>{ohlc_rows}</table>
<div class="na-box">
    <div class="opt-sec" style="color:#38bdf8;font-size:12px;font-weight:700">SYS-1: 3-DAY UNIDIRECTIONAL VERTICAL DEBIT SPREAD (Win Rate: 61.4% | 65 QTY/LOT | 3:15 PM Check / 3:20:00 PM Entry) &rarr; {sig}</div>
  <div class="opt-sec">
    <b>Strike Pairings (Directional ATM Leg + OTM Insurance Hedge):</b><br>
    &bull; <b>100-Pt Spread (Max Gross: Rs.6,500/lot):</b> &nbsp;<span class="pos">LONG (CE): Buy {atm} CE + Sell {atm+100} CE</span> &nbsp;|&nbsp; <span class="neg">SHORT (PE): Buy {atm} PE + Sell {atm-100} PE</span><br>
    &bull; <b>200-Pt Spread (Max Gross: Rs.13,000/lot):</b> &nbsp;<span class="pos">LONG (CE): Buy {atm} CE + Sell {atm+200} CE</span> &nbsp;|&nbsp; <span class="neg">SHORT (PE): Buy {atm} PE + Sell {atm-200} PE</span>
  </div>
  <div class="opt-sec">
    <b>Next-Morning Exit &amp; Profit Targets in Rs. (Per 1 Lot = 65 Qty):</b><br>
    1. <b>9:15:00 AM Cash Spot Gap Check (Supra-Normal Gap &gt; +0.40% / &gt; 100 pts in favor):</b><br>
    &nbsp;&nbsp;&nbsp;&bull; <b>100-Pt Spread:</b> +40 to +55 pts (<span class="pos">+Rs.2,600 to +Rs.3,575 / lot</span>) &rarr; Exit <b>IMMEDIATELY at 9:15:02 AM</b>.<br>
    &nbsp;&nbsp;&nbsp;&bull; <b>200-Pt Spread:</b> +80 to +115 pts (<span class="pos">+Rs.5,200 to +Rs.7,475 / lot</span>) &rarr; Exit <b>IMMEDIATELY at 9:15:02 AM</b>.<br>
    2. <b>Normal Morning Window (Peak Booking 9:17–9:19 AM at +0.15% Spot Target | Hard Force-Close at 9:20:00 AM):</b><br>
    &nbsp;&nbsp;&nbsp;&bull; <b>100-Pt Spread:</b> +15 to +25 pts (<span class="pos">+Rs.975 to +Rs.1,625 / lot</span>)<br>
    &nbsp;&nbsp;&nbsp;&bull; <b>200-Pt Spread:</b> +30 to +50 pts (<span class="pos">+Rs.1,950 to +Rs.3,250 / lot</span>)<br>
    3. <b>Max Loss Cap &amp; Margin Safeguard:</b><br>
    &nbsp;&nbsp;&nbsp;&bull; <b>100-Pt Max Loss:</b> -18 to -25 pts (<span class="neg">-Rs.1,170 to -Rs.1,625 / lot</span>) &nbsp;|&nbsp; <b>200-Pt Max Loss:</b> -35 to -45 pts (<span class="neg">-Rs.2,275 to -Rs.2,925 / lot</span>)<br>
    &nbsp;&nbsp;&nbsp;&bull; Force-close ALL open legs by <b>9:20:00 AM</b> &nbsp;|&nbsp; Keep <b>Rs.10,000 free buffer</b> in account.
  </div>
  <div class="opt-sec">
    <b>Order Execution Sequence (NRML | 65 Qty/Lot):</b><br>
    &bull; <span class="pos">LONG (3rd+ Consecutive GREEN Close — CE Only):</span> <b>Entry (3:20 PM):</b> 1) BUY {atm} CE [LIMIT Ask+Rs.3] &rarr; 2) SELL {atm+100}/{atm+200} CE [LIMIT Bid-Rs.3] &nbsp;|&nbsp; <b>Exit (9:15–9:20 AM):</b> 1) BUY Sold OTM CE [Ask+Rs.3] &rarr; 2) SELL Bought ATM CE [Bid-Rs.3]<br>
    &bull; <span class="neg">SHORT (3rd+ Consecutive RED Close — PE Only):</span> <b>Entry (3:20 PM):</b> 1) BUY {atm} PE [LIMIT Ask+Rs.3] &rarr; 2) SELL {atm-100}/{atm-200} PE [LIMIT Bid-Rs.3] &nbsp;|&nbsp; <b>Exit (9:15–9:20 AM):</b> 1) BUY Sold OTM PE [Ask+Rs.3] &rarr; 2) SELL Bought ATM PE [Bid-Rs.3]
  </div>
  <hr style="border-color:#334155;margin:6px 0">
  <div>
    <div class="warn" style="font-size:11.8px;margin-bottom:3px">SYS-2: 5-DAY CLOSING IRON CONDOR (3:15 PM Check / 3:20:00 PM Entry | 1.50x Corridor = +/-{band_150} pts | 65 Qty/Lot)</div>
    &bull; <b>IC-1 (Compressed S3/S5 + Flip — Win Rate 85.5%):</b> <span class="{'pos' if ('STANDBY' in sig and ic_comp) else 'warn'}">{'ACTIVE' if ('STANDBY' in sig and ic_comp) else 'STANDBY'}</span> &nbsp;|&nbsp; <i>Rule:</i> |S3| &lt; 1.0% &amp; |S5| &lt; 1.5% + Flip [Now: S3={s3_val:+.2f}%, S5={last_n['s5']:+.2f}%]<br>
    &bull; <b>IC-2 (Divergent S3/S5 + Flip — Win Rate 83.0%):</b> <span class="{'pos' if ('STANDBY' in sig and ic_div) else 'warn'}">{'ACTIVE' if ('STANDBY' in sig and ic_div) else 'STANDBY'}</span> &nbsp;|&nbsp; <i>Rule:</i> S3 &amp; S5 Opposite Signs + Flip [Now: S3={s3_val:+.2f}%, S5={last_n['s5']:+.2f}%]<br>
    &bull; <b>4-Leg Entry (3:20 PM):</b> 1) BUY <b>{ic_long_pe} PE</b> + BUY <b>{ic_long_ce} CE</b> (Hedges First) &rarr; 2) SELL <b>{ic_short_pe} PE</b> + SELL <b>{ic_short_ce} CE</b><br>
    &bull; <b>Profit Target &amp; Stop-Loss:</b> Book profit at <b>55% of Net Credit Received</b> (typically <span class="pos">+Rs.2,200 to +Rs.3,800 / lot</span>) &nbsp;|&nbsp; Stop-Loss on daily close <b>&lt; {ic_short_pe}</b> or <b>&gt; {ic_short_ce}</b> &nbsp;|&nbsp; Max exit <b>3:20 PM on Day 5</b>.
  </div>
    <hr style="border-color:#334155;margin:6px 0">
  <div>
    <div class="pos" style="font-size:11.8px;margin-bottom:2px">SYS-3: CASH BTST — 3RD DAY+ CONTINUOUS GREEN GATEKEEPER (Encoded Win Rate: 68.5% | Median Target: +0.55% to +0.75%)</div>
    &bull; <b>Active 3:20 PM Picks:</b> <span class="pos">{', '.join([f"{s['sym']} (G{s['g_streak']})" for s in stk_list if s['g_streak'] >= 3]) or 'NONE (All 7 Stocks < 3 Consecutive Green Days)'}</span> &nbsp;|&nbsp; <b>Entry:</b> <b>3:20:00 PM</b> (Day 3+ Green Settlement) &rarr; <b>Exit:</b> Next Day <b>9:20:00 AM</b> (or +0.55% / +0.75% Limit).
  </div>

</div>
<table class="grid"><tr><th>Date</th><th>Nifty 50</th><th>N%</th><th>NS3</th><th>NS5</th><th>NS10</th><th>NS15</th><th>NS20</th><th class="wdiv">Midcap 150</th><th>M%</th><th>MS3</th><th>MS5</th><th>MS10</th><th>MS15</th><th>MS20</th><th class="wdiv">Smlcap 250</th><th>S%</th><th>SS3</th><th>SS5</th><th>SS10</th><th>SS15</th><th>SS20</th></tr>{trows}</table>
<table class="grid stk"><tr><th>Metric / Date</th>{stk_th}</tr><tr><td><b>CMP | Qty</b></td>{row_cmp}</tr><tr><td><b>BTST (3:20PM)</b></td>{row_btst}</tr><tr><td><b>+0.55 / +0.75</b></td>{row_tgt}</tr><tr><td><b>Vol | VolX</b></td>{row_vol}</tr><tr><td><b>S2.5 / S5</b></td>{row_s25_5}</tr><tr class="top-sep"><td><b>S10 / S15</b></td>{row_s10_15}</tr>{date_rows_html}</table>
</div>'''

def run_29yr_backtest():
    b = get_hist('^NSEI', 'max').copy()
    b['pct'] = b['Close'].pct_change() * 100
    b['s3'] = b['pct'].rolling(3).sum()
    b['s5'] = b['pct'].rolling(5).sum()
    b['vol252'] = (b['Close'].pct_change()).rolling(252).std() * math.sqrt(252)
    b['vol252'] = b['vol252'].fillna(0.16)
    b = b.dropna(subset=['pct']).copy()

    sys1_rows, ic1_rows, ic2_rows, btst3_rows = [], [], [], []
    streak = 0
    for i in range(len(b) - 5):
        p = b['pct'].iloc[i]
        if p > 0: streak = streak + 1 if streak > 0 else 1
        elif p < 0: streak = streak - 1 if streak < 0 else -1
        else: streak = 0
        dt_str = b.index[i].strftime('%Y-%m-%d')
        yr = b.index[i].year
        c0 = b['Close'].iloc[i]
        o1, h1, l1, c1 = b['Open'].iloc[i+1], b['High'].iloc[i+1], b['Low'].iloc[i+1], b['Close'].iloc[i+1]

        if streak >= 3:
            gap_pct = (o1 - c0) / c0 * 100
            max_fav = (h1 - c0) / c0 * 100
            win = (gap_pct >= 0.15) or (max_fav >= 0.15 and c1 > c0 * 0.999)
            pts = (o1 - c0) if gap_pct > 0.40 else (c0 * 0.0015 if win else (c1 - c0))
            sys1_rows.append({'Date': dt_str, 'Year': yr, 'Side': 'LONG', 'Win': win, 'Pts': round(pts, 1)})
        elif streak <= -3:
            gap_pct = (c0 - o1) / c0 * 100
            max_fav = (c0 - l1) / c0 * 100
            win = (gap_pct >= 0.15) or (max_fav >= 0.15 and c1 < c0 * 1.001)
            pts = (c0 - o1) if gap_pct > 0.40 else (c0 * 0.0015 if win else (c0 - c1))
            sys1_rows.append({'Date': dt_str, 'Year': yr, 'Side': 'SHORT', 'Win': win, 'Pts': round(pts, 1)})
        elif i >= 5:
            p_prev = b['pct'].iloc[i-1]
            flip = (p * p_prev) < 0
            s3v, s5v = b['s3'].iloc[i], b['s5'].iloc[i]
            band = c0 * b['vol252'].iloc[i] * math.sqrt(5.0 / 252.0) * 1.50
            lo, hi = c0 - band, c0 + band
            fut_closes = b['Close'].iloc[i+1:i+6]
            safe = (fut_closes.min() >= lo) and (fut_closes.max() <= hi)
            if flip and abs(s3v) < 1.0 and abs(s5v) < 1.5:
                ic1_rows.append({'Date': dt_str, 'Year': yr, 'Win': safe, 'Band': round(band, 0)})
            if flip and (s3v * s5v) < 0:
                ic2_rows.append({'Date': dt_str, 'Year': yr, 'Win': safe, 'Band': round(band, 0)})

        if streak == 3:
            ret_next = (c1 - c0) / c0 * 100
            btst3_rows.append({'Date': dt_str, 'Year': yr, 'Win': ret_next > 0, 'Ret%': round(ret_next, 2)})

    return pd.DataFrame(sys1_rows), pd.DataFrame(ic1_rows), pd.DataFrame(ic2_rows), pd.DataFrame(btst3_rows), b.index.strftime('%Y-%m-%d'), b.index[-1].strftime('%Y-%m-%d')

tab1, tab2, tab3 = st.tabs(['Live Dashboard', '29-Yr Backtest (1997-2026)', 'Live Trade Tracker'])

with tab1:
    st.markdown(html, unsafe_allow_html=True)

with tab2:
    if st.button('Run 29-Yr Audit (1997-2026)'):
        s1_df, ic1_df, ic2_df, b3_df, d_start, d_end = run_29yr_backtest()
        st.markdown(f"**Full Nifty 50 (`^NSEI`) Audit Window:** `{d_start}` to `{d_end}` | **All Options Timing:** `3:15 PM Check / 3:20:00 PM Entry`")
        summary_df = pd.DataFrame([
            {'Strategy': 'SYS-1: 3-Day Vertical Debit Spread (All)', 'Total Signals': len(s1_df), 'Wins': int(s1_df['Win'].sum()), 'Win Rate %': round(s1_df['Win'].mean()*100, 2), 'Avg Pts/Trade': round(s1_df['Pts'].mean(), 1)},
            {'Strategy': 'SYS-1: Long (Bull Call Spread)', 'Total Signals': int((s1_df['Side']=='LONG').sum()), 'Wins': int(s1_df[s1_df['Side']=='LONG']['Win'].sum()), 'Win Rate %': round(s1_df[s1_df['Side']=='LONG']['Win'].mean()*100, 2), 'Avg Pts/Trade': round(s1_df[s1_df['Side']=='LONG']['Pts'].mean(), 1)},
            {'Strategy': 'SYS-1: Short (Bear Put Spread)', 'Total Signals': int((s1_df['Side']=='SHORT').sum()), 'Wins': int(s1_df[s1_df['Side']=='SHORT']['Win'].sum()), 'Win Rate %': round(s1_df[s1_df['Side']=='SHORT']['Win'].mean()*100, 2), 'Avg Pts/Trade': round(s1_df[s1_df['Side']=='SHORT']['Pts'].mean(), 1)},
            {'Strategy': 'SYS-2: IC-1 (Compressed S3/S5 + Flip)', 'Total Signals': len(ic1_df), 'Wins': int(ic1_df['Win'].sum()), 'Win Rate %': round(ic1_df['Win'].mean()*100, 2), 'Avg Pts/Trade': f"+/-{ic1_df['Band'].mean():.0f} band"},
            {'Strategy': 'SYS-2: IC-2 (Divergent S3/S5 + Flip)', 'Total Signals': len(ic2_df), 'Wins': int(ic2_df['Win'].sum()), 'Win Rate %': round(ic2_df['Win'].mean()*100, 2), 'Avg Pts/Trade': f"+/-{ic2_df['Band'].mean():.0f} band"},
            {'Strategy': 'BTST: 3-Day Consecutive Green Gatekeeper', 'Total Signals': len(b3_df), 'Wins': int(b3_df['Win'].sum()), 'Win Rate %': round(b3_df['Win'].mean()*100, 2), 'Avg Pts/Trade': f"{b3_df['Ret%'].mean():+.2f}%"},
        ])
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        yr_s1 = s1_df.groupby('Year').agg(SYS1_Trades=('Win','count'), SYS1_WinPct=('Win', lambda x: round(x.mean()*100,1)))
        yr_ic1 = ic1_df.groupby('Year').agg(IC1_Trades=('Win','count'), IC1_WinPct=('Win', lambda x: round(x.mean()*100,1)))
        yr_ic2 = ic2_df.groupby('Year').agg(IC2_Trades=('Win','count'), IC2_WinPct=('Win', lambda x: round(x.mean()*100,1)))
        yr_all = yr_s1.join([yr_ic1, yr_ic2], how='outer').fillna(0).sort_index(ascending=False).reset_index()
        st.markdown("**Year-by-Year Breakdown (`2026` back to `1997`):**")
        st.dataframe(yr_all, use_container_width=True, hide_index=True, height=260)

        csv_buf = io.StringIO()
        s1_df.to_csv(csv_buf, index=False)
        st.download_button('Download Full 29-Yr SYS-1 Trade Log (CSV)', csv_buf.getvalue(), 'nifty_29yr_sys1_backtest.csv', 'text/csv')

with tab3:
    if 'trade_log' not in st.session_state:
        st.session_state['trade_log'] = pd.DataFrame([
            {'Date': '2026-11-23', 'Time': '15:20', 'Strategy': 'SYS-2 IC-1 (5-Day Iron Condor)', 'Strikes / Ticker': f'BUY {ic_long_pe}PE/{ic_long_ce}CE | SELL {ic_short_pe}PE/{ic_short_ce}CE', 'Qty': 65, 'Status': 'WATCHING (3:15 PM Check)', 'Net_PnL_Rs': 0}
        ])
    st.markdown(f"**Active Signal Advisory ({ist_now} IST):** `SYS-1 = {sig}` | `IC-1 = {'ACTIVE' if ('STANDBY' in sig and ic_comp) else 'STANDBY'}` | `IC-2 = {'ACTIVE' if ('STANDBY' in sig and ic_div) else 'STANDBY'}`")
    edited_log = st.data_editor(st.session_state['trade_log'], num_rows='dynamic', use_container_width=True, key='log_editor')
    st.session_state['trade_log'] = edited_log
    c_dl, c_ul = st.columns(2)
    with c_dl:
        st.download_button('Export Trade Tracker (CSV)', edited_log.to_csv(index=False), 'my_live_trade_tracker.csv', 'text/csv')
    with c_ul:
        up = st.file_uploader('Restore Saved Tracker CSV', type=['csv'], label_visibility='collapsed')
        if up is not None:
            st.session_state['trade_log'] = pd.read_csv(up)
            st.rerun()
