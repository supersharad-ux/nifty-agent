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
    sub = df.tail(6)
    if not stk_dates: stk_dates = sub.index.strftime('%Y-%m-%d').tolist()
    last_st = sub.iloc[-1]
    cmp = last_st['Close']
    stk_list.append({
        'sym': sym, 'uni': uni, 'cmp': cmp, 'qty': max(1, int(35000 // cmp)),
        'vol_m': last_st['Volume'] / 1e6, 'vol_x': vol_x,
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

ist_now = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
html = f'''<div style="background:#0b1120;color:#e2e8f0;font-family:Segoe UI,Arial,sans-serif;padding:4px 6px;font-size:9.5px;border-radius:6px;overflow-x:auto;-webkit-overflow-scrolling:touch">
