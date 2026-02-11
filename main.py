import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import streamlit.components.v1 as components

# --- 1. ページ設定 ---
st.set_page_config(
    page_title="UMI-MIRU: 海況ダッシュボード",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 拠点データ (北から順 & 不要拠点削除) ---
LOCATIONS = {
    "北海道 別海": {"lat": 43.39, "lon": 145.12, "type": "marine"},
    "北海道 函館": {"lat": 41.76, "lon": 140.74, "type": "marine"},
    "宮城 石巻": {"lat": 38.41, "lon": 141.32, "type": "marine"},
    "福島 相馬": {"lat": 37.83, "lon": 140.95, "type": "marine"},
    "富山 魚津": {"lat": 36.83, "lon": 137.40, "type": "marine"},
    "兵庫 香住": {"lat": 35.64, "lon": 134.63, "type": "marine"},
    "京都 舞鶴": {"lat": 35.60, "lon": 135.30, "type": "marine"},
    "千葉 勝浦": {"lat": 35.15, "lon": 140.32, "type": "marine"}, # デフォルト
    "静岡 焼津": {"lat": 34.86, "lon": 138.33, "type": "marine"},
    "香川 多度津": {"lat": 34.27, "lon": 133.75, "type": "marine"},
    "徳島": {"lat": 34.00, "lon": 134.70, "type": "marine"},
    "福岡 博多": {"lat": 33.60, "lon": 130.40, "type": "marine"},
    "東京": {"lat": 35.66, "lon": 139.79, "type": "weather"}, # 需要予測・風用
}

# --- 3. 関数定義 ---

# 月齢計算
def calculate_moon_age(date):
    known_new_moon = datetime(2000, 1, 6).date()
    days_diff = (date - known_new_moon).days
    moon_age = days_diff % 29.53059
    return round(moon_age, 1)

def get_tide_name(moon_age):
    ma = round(moon_age)
    if ma in [0, 1, 2, 14, 15, 16, 29, 30]: return "大潮"
    elif ma in [3, 4, 5, 17, 18, 19]: return "中潮"
    elif ma in [6, 7, 8, 9, 20, 21, 22, 23]: return "小潮"
    elif ma in [10, 11, 12, 24, 25, 26]: return "長潮/若潮"
    else: return "中潮"

# APIデータ取得
@st.cache_data(ttl=3600)
def get_marine_data(lat, lon, days=3):
    url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=wave_height,wind_speed_10m,wind_direction_10m&forecast_days={days}&timezone=Asia%2FTokyo"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon, days=4):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max&forecast_days={days}&timezone=Asia%2FTokyo&wind_speed_unit=ms"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

def get_wave_status_text(wave_height):
    if wave_height is None: return "不明"
    if wave_height >= 2.5: return "時化"
    elif wave_height >= 1.5: return "注意"
    else: return "凪"

def get_tokyo_demand_prediction(tokyo_weather_data):
    if not tokyo_weather_data or 'daily' not in tokyo_weather_data:
        return "データなし"
    daily_data = tokyo_weather_data['daily']
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_index = -1
    for i, date_str in enumerate(daily_data['time']):
        if date_str == today_str:
            today_index = i
            break
    recommendation = []
    if today_index != -1:
        temp_today_max = daily_data['temperature_2m_max'][today_index]
        if temp_today_max < 10: recommendation.append("気温低下(鍋)")
        precip_prob = daily_data['precipitation_probability_max'][today_index]
        if precip_prob >= 50: recommendation.append(f"雨{precip_prob}%(客足)")
    if recommendation: return " / ".join(recommendation)
    return "特になし"

# --- 4. メイン画面レイアウト ---

st.title("🌊 UMI-MIRU: 海況・漁場監視")

# [A] 実況天気図 (Tenki.jpの画像を直接表示)
# 理由: 気象庁公式はスクレイピング対策が厳しいため、安定しているTenki.jp(日本気象協会)の画像を使用
st.subheader("📡 実況天気図")
weather_map_url = "https://static.tenki.jp/static-images/chart/current/large.jpg"

st.markdown(
    f"""
    <div style="text-align: center;">
        <img src="{weather_map_url}" style="width: 100%; max-width: 800px; border-radius: 10px;">
        <p style="font-size: 0.8em; color: gray;">出典: tenki.jp (日本気象協会)</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Sidebar
st.sidebar.header("設定")
marine_keys = [k for k, v in LOCATIONS.items() if v["type"] == "marine"]
default_index = 0
if "千葉 勝浦" in marine_keys: default_index = marine_keys.index("千葉 勝浦")
selected_location = st.sidebar.selectbox("詳細を表示する拠点", marine_keys, index=default_index)
st.sidebar.button("データを更新")

# Main Area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📊 産地別・海況マトリックス")
    marine_matrix_data = []
    dates = [(datetime.now() + timedelta(days=i)).date() for i in range(3)]
    date_cols = [date.strftime('%m/%d') for date in dates]

    for loc_name in marine_keys:
        loc_data = LOCATIONS[loc_name]
        marine_data = get_marine_data(loc_data["lat"], loc_data["lon"])
        if marine_data and 'hourly' in marine_data:
            row_data = {"拠点": loc_name}
            for i, date in enumerate(dates):
                current_day_indices = [j for j, time_str in enumerate(marine_data['hourly']['time']) if datetime.fromisoformat(time_str).date() == date]
                if current_day_indices:
                    daily_waves = [marine_data['hourly']['wave_height'][j] for j in current_day_indices if marine_data['hourly']['wave_height'][j] is not None]
                    if daily_waves:
                        avg_wave = np.mean(daily_waves)
                        status_text = get_wave_status_text(avg_wave)
                        moon_age_val = calculate_moon_age(date)
                        tide_name = get_tide_name(moon_age_val)
                        row_data[date_cols[i]] = f"{status_text} {avg_wave:.1f}m ({tide_name}, 月齢{moon_age_val:.1f})"
                    else: row_data[date_cols[i]] = "データなし"
                else: row_data[date_cols[i]] = "-"
            marine_matrix_data.append(row_data)
        else: marine_matrix_data.append({"拠点": loc_name, **{d: "取得失敗" for d in date_cols}})

    marine_df = pd.DataFrame(marine_matrix_data)
    if not marine_df.empty:
        marine_df.set_index("拠点", inplace=True)
        def highlight_status(val):
            val_str = str(val)
            color = 'black'; weight = 'normal'
            if '時化' in val_str: color = 'red'; weight = 'bold'
            elif '注意' in val_str: color = 'orange'; weight = 'bold'
            elif '凪' in val_str: color = 'blue'; weight = 'bold'
            return f'color: {color}; font-weight: {weight}'
        st.dataframe(marine_df.style.map(highlight_status), use_container_width=True, height=500)

    st.markdown("---")
    st.subheader(f"📈 {selected_location} の詳細推移")
    sel_data = LOCATIONS[selected_location]
    sel_marine = get_marine_data(sel_data["lat"], sel_data["lon"])
    if sel_marine and 'hourly' in sel_marine:
        df_sel = pd.DataFrame(sel_marine['hourly'])
        df_sel['time'] = pd.to_datetime(df_sel['time'])
        df_sel = df_sel.set_index('time')
        end_time = datetime.now() + timedelta(days=3)
        df_sel = df_sel[df_sel.index <= end_time]
        st.line_chart(df_sel['wave_height'].rename("波高(m)"))
        st.line_chart(df_sel['wind_speed_10m'].rename("風速(m/s)"))
    else: st.error("データ取得失敗")

with col2:
    st.header("🗼 東京マーケット & 風予報")
    tokyo_loc = LOCATIONS["東京"]
    tokyo_weather = get_weather_data(tokyo_loc["lat"], tokyo_loc["lon"])
    if tokyo_weather:
        st.subheader("需要予測")
        demand_text = get_tokyo_demand_prediction(tokyo_weather)
        st.info(demand_text)
        
        st.subheader("⚠️ 出荷現場の風予報 (1時間毎)")
        hourly_df = pd.DataFrame(tokyo_weather['hourly'])
        hourly_df['time'] = pd.to_datetime(hourly_df['time'])
        now = datetime.now()
        hourly_df = hourly_df[hourly_df['time'] >= now]
        display_df = hourly_df.head(24).copy()
        display_df['time_str'] = display_df['time'].dt.strftime('%H:%M')
        display_df = display_df.set_index('time_str')
        display_df['wind_speed_10m'] = display_df['wind_speed_10m'].round(1)
        
        def highlight_wind(val):
            color = ''
            if val >= 10: color = 'background-color: #ffcccc'
            elif val >= 5: color = 'background-color: #ffffcc'
            return color
        
        st.dataframe(display_df[['wind_speed_10m']].rename(columns={'wind_speed_10m': '風速(m/s)'}).style.map(highlight_wind).format("{:.1f}"), height=400, use_container_width=True)
        
        max_wind_24h = display_df['wind_speed_10m'].max()
        if max_wind_24h >= 10: st.error(f"🔴 今後24時間: 最大{max_wind_24h:.1f}m/s の強風予報")
        elif max_wind_24h >= 5: st.warning(f"🟡 今後24時間: 最大{max_wind_24h:.1f}m/s の風あり")
        else: st.success("🔵 今後24時間は穏やか")
        
        if 'daily' in tokyo_weather:
            daily_tokyo = pd.DataFrame(tokyo_weather['daily'])
            daily_tokyo['time'] = pd.to_datetime(daily_tokyo['time']).dt.strftime('%m/%d')
            daily_tokyo.set_index('time', inplace=True)
            st.write("週間天気:")
            st.dataframe(daily_tokyo[['temperature_2m_max', 'temperature_2m_min', 'precipitation_probability_max']].rename(columns={'temperature_2m_max': '最高', 'temperature_2m_min': '最低', 'precipitation_probability_max': '降水%'}).T)
    else: st.warning("東京のデータ取得不可")

# [E] Windy.com
st.markdown("---")
st.subheader("🌍 Windy.com (風・波の動向)")
components.html(
    """<iframe width="100%" height="450" src="https://embed.windy.com/embed2.html?lat=35.6895&lon=139.6917&zoom=5&overlay=waves&product=ecmwf&level=surface&menu=&message=&marker=&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=default&metricTemp=default&radarRange=-1" frameborder="0"></iframe>""",
    height=450,
)

# [F] 画像 (wsrv.nl プロキシを経由してHTMLで直接表示)
st.markdown("---")
st.subheader("🌡️ 海面水温 & 🌊 波浪実況")
col_img1, col_img2 = st.columns(2)

# wsrv.nl を使うことで、気象庁のサーバー制限(403)を回避して表示する
def get_proxy_url(url):
    clean_url = url.replace("https://", "")
    return f"https://wsrv.nl/?url={clean_url}&output=webp"

with col_img1:
    sst_url = "https://www.data.jma.go.jp/gmd/kaikyou/kaikyou/tile/jp/png/sst_now.png"
    st.markdown(
        f"""
        <div style="text-align: center;">
            <p><b>海面水温図</b></p>
            <img src="{get_proxy_url(sst_url)}" style="width: 100%; border-radius: 5px;" alt="海面水温図読み込みエラー">
        </div>
        """,
        unsafe_allow_html=True
    )

with col_img2:
    wave_url = "https://www.data.jma.go.jp/gmd/waveinf/tile/jp/png/p_now.png"
    st.markdown(
        f"""
        <div style="text-align: center;">
            <p><b>全国波浪実況図</b></p>
            <img src="{get_proxy_url(wave_url)}" style="width: 100%; border-radius: 5px;" alt="波浪実況図読み込みエラー">
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")
st.link_button("気象庁 公式防災情報", "https://www.jma.go.jp/bosai/map.html")