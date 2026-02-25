import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import streamlit.components.v1 as components
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# --- 1. ページ設定 ---
st.set_page_config(page_title="UMI-MIRU: 水産お天気ダッシュボード", layout="wide")

# --- 2. 拠点データ (緯度順) ---
LOCATIONS = {
    "北海道 別海": {"lat": 43.39, "lon": 145.12, "type": "marine"},
    "北海道 函館": {"lat": 41.76, "lon": 140.74, "type": "marine"},
    "福島 相馬": {"lat": 37.83, "lon": 140.95, "type": "marine"},
    "富山 魚津": {"lat": 36.83, "lon": 137.40, "type": "marine"},
    "兵庫 香住": {"lat": 35.64, "lon": 134.63, "type": "marine"},
    "京都 舞鶴": {"lat": 35.60, "lon": 135.30, "type": "marine"},
    "千葉 勝浦": {"lat": 35.15, "lon": 140.32, "type": "marine"},
    "東京 品川": {"lat": 35.61, "lon": 139.78, "type": "marine"},
    "徳島 鳴門": {"lat": 34.23, "lon": 134.64, "type": "marine"},
    "福岡 博多": {"lat": 33.60, "lon": 130.40, "type": "marine"},
    "東京": {"lat": 35.66, "lon": 139.79, "type": "weather"},
}

# --- 3. 関数定義 ---

@st.cache_data(ttl=1800)
def fetch_api_data(url):
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        return r.json()
    except: return None

def get_weather_desc(code):
    mapping = {0: "☀️ 快晴", 1: "🌤️ 晴", 2: "⛅ 曇晴", 3: "☁️ 曇", 45: "🌫️ 霧", 51: "🌦️ 霧雨", 61: "☔ 小雨", 63: "☔ 雨", 80: "🌧️ 俄雨"}
    return mapping.get(code, "☁️ 不明")

def find_nearest_idx(time_list, target_dt):
    times = pd.to_datetime(time_list)
    diffs = [(t.replace(tzinfo=None) - target_dt.replace(tzinfo=None)).total_seconds() for t in times]
    return np.argmin(np.abs(diffs))

def calculate_moon_age(date):
    known_new_moon = datetime(2000, 1, 6).date()
    days_diff = (date - known_new_moon).days
    return round(days_diff % 29.53059, 1)

def get_tide_char(moon_age):
    ma = round(moon_age)
    if ma in [0, 1, 2, 14, 15, 16, 29, 30]: return "大"
    elif ma in [3, 4, 5, 17, 18, 19]: return "中"
    elif ma in [6, 7, 8, 9, 20, 21, 22, 23]: return "小"
    else: return "長"

# --- 4. メイン画面 ---
st.title("🌊 UMI-MIRU: 水産お天気ダッシュボード")

# [A] WINDY
st.subheader("🌍 広域マップ")
tab1, tab2, tab3 = st.tabs(["🍃 風・気圧", "🌊 波浪", "🌡️ 水温"])
windy_style = 'style="width: 100%; height: 380px; border-radius: 8px; border: none;"'
def windy_url(ov): return f"https://embed.windy.com/embed2.html?lat=36.5&lon=137.0&zoom=5&level=surface&overlay={ov}&product=ecmwf&menu=&message=&marker=&calendar=now&pressure=true&type=map&location=coordinates&detail=&metricWind=default&metricTemp=default&radarRange=-1"

with tab1: components.html(f'<iframe src="{windy_url("wind")}" {windy_style}></iframe>', height=380)
with tab2: components.html(f'<iframe src="{windy_url("waves")}" {windy_style}></iframe>', height=380)
with tab3: components.html(f'<iframe src="{windy_url("sst")}" {windy_style}></iframe>', height=380)

st.markdown("---")

# [B] 東京情報 & 現場アラート
st.subheader("🗼 東京需要 & 出荷現場")
tokyo_url = f"https://api.open-meteo.com/v1/forecast?latitude=35.66&longitude=139.79&hourly=temperature_2m,wind_speed_10m,precipitation&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&forecast_days=3&timezone=Asia%2FTokyo&wind_speed_unit=ms"
tokyo_data = fetch_api_data(tokyo_url)

if tokyo_data:
    now_dt = datetime.now()
    idx_now = find_nearest_idx(tokyo_data['hourly']['time'], now_dt)
    
    # 現場アラート (重要：強風・低温)
    wind_now = tokyo_data['hourly']['wind_speed_10m'][idx_now]
    temp_min_today = tokyo_data['daily']['temperature_2m_min'][0]
    
    # 強風警告ロジック
    if wind_now >= 10:
        st.error(f"🌪️ **強風警告：{wind_now:.1f}m/s** 発泡が飛散し非常に危険です！荷役を中止してください。")
    elif wind_now >= 5:
        st.warning(f"🍃 **風注意：{wind_now:.1f}m/s** 発泡スチロールが飛び始めます。固定を確認してください。")
    
    # 低温・鍋需要
    if temp_min_today <= 12:
        st.info(f"🍲 **需要予測：低温（{temp_min_today:.1f}℃）** 鍋物用商材（白身魚・貝類）の引きが強まります。")

    # 週間天気
    st.write("📅 **東京 週間天気**")
    df_week = pd.DataFrame({
        "日付": [d[5:] for d in tokyo_data['daily']['time']],
        "天気": [get_weather_desc(c) for c in tokyo_data['daily']['weather_code']],
        "最高": tokyo_data['daily']['temperature_2m_max'],
        "最低": tokyo_data['daily']['temperature_2m_min']
    }).set_index("日付")
    st.dataframe(df_week.T, width="stretch")

    # 風速予測
    st.write("🍃 **出荷現場 風速予測 (m/s)**")
    wind_h = pd.DataFrame({
        "時間": [t[11:16] for t in tokyo_data['hourly']['time']],
        "風速": tokyo_data['hourly']['wind_speed_10m']
    }).iloc[idx_now:idx_now+12].set_index("時間")
    st.dataframe(wind_h.T, width="stretch")

    # 降水グラフ
    st.write("☔ **降水予報推移 (mm)**")
    rain_slice = pd.DataFrame({"t": pd.to_datetime(tokyo_data['hourly']['time']), "v": tokyo_data['hourly']['precipitation']}).iloc[idx_now:idx_now+15]
    fig_r, ax_r = plt.subplots(figsize=(8, 2.5))
    ax_r.bar(rain_slice['t'], rain_slice['v'], color='#1f77b4', width=0.03)
    ax_r.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax_r.set_ylabel("Rain (mm)")
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    st.pyplot(fig_r)
    plt.close()

st.markdown("---")

# [C] 全国海況予報 (北→南)
st.subheader("📊 全国海況予報 (北→南)")
m_age = calculate_moon_age(datetime.now().date())
st.write(f"🌙 **本日の月齢: {m_age} ({get_tide_char(m_age)}潮)**")

marine_keys = [k for k, v in LOCATIONS.items() if v["type"] == "marine"]
marine_keys.sort(key=lambda x: LOCATIONS[x]["lat"], reverse=True)

matrix_list = []
dates = [datetime.now().date() + timedelta(days=i) for i in range(3)]

with st.spinner('漁場データ更新中...'):
    for name in marine_keys:
        lat, lon = LOCATIONS[name]["lat"], LOCATIONS[name]["lon"]
        m_data = fetch_api_data(f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=wave_height&forecast_days=3&timezone=Asia%2FTokyo")
        w_data = fetch_api_data(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=wind_speed_10m&forecast_days=3&timezone=Asia%2FTokyo&wind_speed_unit=ms")
        row = {"拠点": name}
        for d in dates:
            target_dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=12)
            wv, wd = 0.0, 0.0
            if m_data: wv = m_data['hourly']['wave_height'][find_nearest_idx(m_data['hourly']['time'], target_dt)] or 0.0
            if w_data: wd = w_data['hourly']['wind_speed_10m'][find_nearest_idx(w_data['hourly']['time'], target_dt)] or 0.0
            
            # 状態判定
            status = "🟢凪"
            if wv >= 2.5 or wd >= 10: status = "🔴時化"
            elif wv >= 1.5 or wd >= 7: status = "🟡注意"
            
            row[d.strftime('%m/%d')] = f"{status} {wv:.1f}/{wd:.0f}({get_tide_char(calculate_moon_age(d))})"
        matrix_list.append(row)

if matrix_list:
    df_matrix = pd.DataFrame(matrix_list).set_index("拠点")
    # 色分けを確実に反映
    def style_status(val):
        if '🔴' in str(val): return 'color: red; font-weight: bold;'
        if '🟡' in str(val): return 'color: orange;'
        if '🟢' in str(val): return 'color: blue;'
        return ''
    st.dataframe(df_matrix.style.applymap(style_status), width="stretch")

st.markdown("---")

# [D] 拠点詳細
st.subheader("📈 拠点詳細推移")
selected_port = st.selectbox("詳しく見る拠点を選択", marine_keys, index=marine_keys.index("千葉 勝浦"))

p_lat, p_lon = LOCATIONS[selected_port]["lat"], LOCATIONS[selected_port]["lon"]
det_m = fetch_api_data(f"https://marine-api.open-meteo.com/v1/marine?latitude={p_lat}&longitude={p_lon}&hourly=wave_height&forecast_days=3&timezone=Asia%2FTokyo")
det_w = fetch_api_data(f"https://api.open-meteo.com/v1/forecast?latitude={p_lat}&longitude={p_lon}&hourly=wind_speed_10m&forecast_days=3&timezone=Asia%2FTokyo&wind_speed_unit=ms")

if det_m and det_w:
    m_df = pd.DataFrame({"t": pd.to_datetime(det_m['hourly']['time']), "v": det_m['hourly']['wave_height']})
    w_df = pd.DataFrame({"t": pd.to_datetime(det_w['hourly']['time']), "v": det_w['hourly']['wind_speed_10m']})
    
    fig_d, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5.5))
    ax1.plot(m_df['t'], m_df['v'], color='blue', linewidth=2)
    ax1.set_ylabel("Wave (m)")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    
    ax2.plot(w_df['t'], w_df['v'], color='green', linewidth=2)
    ax2.set_ylabel("Wind (m/s)")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    plt.tight_layout()
    st.pyplot(fig_d)
    plt.close()