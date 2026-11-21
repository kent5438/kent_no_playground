"""
Module 1: 中央氣象署 (CWA) 與即時氣象預報服務模組
- 支援台灣各縣市鄉鎮區切換 (預設：新竹縣竹東鎮)
- 即時資料來源優先順序：
  1. 若已設定 CWA_API_KEY：串接中央氣象署 Open Data API + Open-Meteo 精確逐時/每週資料
  2. 未設定 CWA_API_KEY 時：自動串接 Open-Meteo 即時真實氣象 API（免 API Key，依精確經緯度與 Asia/Taipei 時區取得即時實測氣溫、逐時 36 小時與未來 7 天真實預報）
  3. 僅在完全斷網無法連線時，才降級為離線備援模型
"""
import hashlib
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from backend.core.config import Config
from backend.core.database import get_db, get_settings
from backend.core.module_registry import BaseModule

# 台灣完整縣市與熱門鄉鎮區清單 (含座標，連動外食推薦也可一鍵同步)
TAIWAN_LOCATIONS: Dict[str, List[Dict[str, Any]]] = {
    "新竹縣": [
        {"town": "竹東鎮", "lat": 24.7376, "lng": 121.0887},
        {"town": "竹北市", "lat": 24.8383, "lng": 121.0086},
        {"town": "湖口鄉", "lat": 24.9039, "lng": 121.0436},
        {"town": "新豐鄉", "lat": 24.8996, "lng": 120.9840},
        {"town": "新埔鎮", "lat": 24.8280, "lng": 121.0728},
        {"town": "關西鎮", "lat": 24.7924, "lng": 121.1764},
        {"town": "芎林鄉", "lat": 24.7755, "lng": 121.0805},
        {"town": "寶山鄉", "lat": 24.7610, "lng": 120.9885},
        {"town": "北埔鄉", "lat": 24.6997, "lng": 121.0583},
        {"town": "橫山鄉", "lat": 24.7208, "lng": 121.1162},
        {"town": "峨眉鄉", "lat": 24.6875, "lng": 121.0169},
        {"town": "尖石鄉", "lat": 24.7069, "lng": 121.2028},
        {"town": "五峰鄉", "lat": 24.6290, "lng": 121.1011},
    ],
    "新竹市": [
        {"town": "東區", "lat": 24.7887, "lng": 121.0003},
        {"town": "北區", "lat": 24.8165, "lng": 120.9571},
        {"town": "香山區", "lat": 24.7634, "lng": 120.9248},
    ],
    "臺北市": [
        {"town": "信義區", "lat": 25.0330, "lng": 121.5654},
        {"town": "大安區", "lat": 25.0268, "lng": 121.5435},
        {"town": "中山區", "lat": 25.0645, "lng": 121.5256},
        {"town": "內湖區", "lat": 25.0830, "lng": 121.5944},
        {"town": "中正區", "lat": 25.0324, "lng": 121.5183},
        {"town": "士林區", "lat": 25.0928, "lng": 121.5198},
    ],
    "新北市": [
        {"town": "板橋區", "lat": 25.0114, "lng": 121.4581},
        {"town": "新店區", "lat": 24.9675, "lng": 121.5419},
        {"town": "中和區", "lat": 24.9994, "lng": 121.4939},
        {"town": "淡水區", "lat": 25.1695, "lng": 121.4411},
        {"town": "林口區", "lat": 25.0775, "lng": 121.3894},
    ],
    "桃園市": [
        {"town": "中壢區", "lat": 24.9652, "lng": 121.2249},
        {"town": "桃園區", "lat": 24.9937, "lng": 121.3010},
        {"town": "龍潭區", "lat": 24.8633, "lng": 121.2133},
        {"town": "楊梅區", "lat": 24.9094, "lng": 121.1458},
    ],
    "苗栗縣": [
        {"town": "頭份市", "lat": 24.6868, "lng": 120.9056},
        {"town": "竹南鎮", "lat": 24.6852, "lng": 120.8736},
        {"town": "苗栗市", "lat": 24.5602, "lng": 120.8214},
    ],
    "臺中市": [
        {"town": "西屯區", "lat": 24.1652, "lng": 120.6358},
        {"town": "北屯區", "lat": 24.1823, "lng": 120.6865},
        {"town": "南屯區", "lat": 24.1387, "lng": 120.6409},
        {"town": "西區", "lat": 24.1414, "lng": 120.6632},
    ],
    "臺南市": [
        {"town": "東區", "lat": 22.9804, "lng": 120.2240},
        {"town": "中西區", "lat": 22.9922, "lng": 120.1974},
        {"town": "永康區", "lat": 23.0258, "lng": 120.2546},
        {"town": "善化區", "lat": 23.1333, "lng": 120.2968},
    ],
    "高雄市": [
        {"town": "左營區", "lat": 22.6901, "lng": 120.2930},
        {"town": "鼓山區", "lat": 22.6487, "lng": 120.2747},
        {"town": "三民區", "lat": 22.6484, "lng": 120.3282},
        {"town": "前鎮區", "lat": 22.5880, "lng": 120.3081},
    ],
    "宜蘭縣": [
        {"town": "宜蘭市", "lat": 24.7570, "lng": 121.7530},
        {"town": "羅東鎮", "lat": 24.6768, "lng": 121.7669},
        {"town": "礁溪鄉", "lat": 24.8240, "lng": 121.7712},
    ],
    "花蓮縣": [
        {"town": "花蓮市", "lat": 23.9872, "lng": 121.6016},
        {"town": "吉安鄉", "lat": 23.9631, "lng": 121.5646},
    ],
}

WIND_DIRECTIONS = ["東北風", "偏東風", "北北東風", "東北東風", "偏北風", "東南東風"]
WEATHER_CONDITIONS = [
    {"pop_max": 15, "desc": "晴時多雲", "icon": "☀️"},
    {"pop_max": 30, "desc": "多雲時晴", "icon": "🌤️"},
    {"pop_max": 50, "desc": "多雲短暫陣雨", "icon": "⛅"},
    {"pop_max": 75, "desc": "陰短暫陣雨", "icon": "🌧️"},
    {"pop_max": 100, "desc": "陰有陣雨", "icon": "⛈️"},
]


def wind_deg_to_zh(deg: Optional[float]) -> str:
    """將風向角度 (0-360°) 轉換為標準中文八方位風向。"""
    if deg is None:
        return "偏東風"
    dirs = ["北風", "東北風", "東風", "東南風", "南風", "西南風", "西風", "西北風"]
    idx = int(((float(deg) + 22.5) % 360) // 45)
    return dirs[idx]


def wind_ms_to_beaufort(ms: float) -> int:
    """依據中央氣象署蒲福風級標準，由風速 (m/s) 換算風力級數。"""
    thresholds = [0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7]
    for scale, limit in enumerate(thresholds):
        if ms < limit:
            return scale
    return 12


def wmo_code_to_zh(code: Optional[int], is_night: bool = False) -> Tuple[str, str]:
    """將 WMO 國際氣象代碼轉換為繁體中文天氣描述與圖示。"""
    c = int(code) if code is not None else 2
    if c == 0:
        return ("晴朗無雲", "🌙" if is_night else "☀️")
    if c == 1:
        return ("晴時多雲", "🌙" if is_night else "🌤️")
    if c == 2:
        return ("多雲時晴", "☁️" if is_night else "⛅")
    if c == 3:
        return ("陰天多雲", "☁️")
    if c in (45, 48):
        return ("有霧或靄", "🌫️")
    if c in (51, 53, 55, 56, 57):
        return ("陰有毛毛雨", "🌦️")
    if c in (61, 80):
        return ("短暫小雨", "🌧️")
    if c in (63, 81):
        return ("陰有陣雨", "🌧️")
    if c in (65, 66, 67, 82):
        return ("陰有大雨", "🌧️")
    if c in (95, 96, 99):
        return ("雷陣雨", "⛈️")
    return ("多雲", "⛅")


def comfort_label(temp_c: float) -> str:
    if temp_c < 15:
        return "偏冷注意保暖"
    if temp_c < 20:
        return "涼爽微冷"
    if temp_c < 25:
        return "舒適宜人"
    if temp_c < 29:
        return "舒適偏暖"
    if temp_c < 33:
        return "悶熱注意防曬"
    return "高溫炎熱多補水"


class WeatherModule(BaseModule):
    module_id = "weather"
    name = "中央氣象署 (CWA) 天氣預報"
    description = "提供未來 24-48 小時逐時預報與未來 7 天每週預報（氣溫、降雨機率/降雨量、風速/風向）"

    def get_locations(self) -> Dict[str, List[Dict[str, Any]]]:
        return TAIWAN_LOCATIONS

    def _resolve_coordinates(self, county: str, town: str, settings: Dict[str, Any]) -> Tuple[float, float]:
        """優先使用使用者微調的精確經緯度（若縣市鄉鎮相同），否則查表取得該鄉鎮中心座標。"""
        if settings and settings.get("county") == county and settings.get("town") == town:
            return float(settings["lat"]), float(settings["lng"])
        for t in TAIWAN_LOCATIONS.get(county, []):
            if t["town"] == town:
                return float(t["lat"]), float(t["lng"])
        return Config.DEFAULT_LAT, Config.DEFAULT_LNG

    def get_forecast(self, county: str = None, town: str = None, force_refresh: bool = False) -> Dict[str, Any]:
        settings = get_settings()
        county = county or settings["county"]
        town = town or settings["town"]
        lat, lng = self._resolve_coordinates(county, town, settings)
        loc_key = f"{county}_{town}"

        if not force_refresh:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT payload_json, source, updated_at FROM weather_cache WHERE location_key = ?",
                    (loc_key,),
                ).fetchone()
                if row:
                    updated_dt = datetime.fromisoformat(row["updated_at"])
                    is_mock_cache = "模擬資料" in (row["source"] or "") or "離線" in (row["source"] or "")
                    # 若快取為真實即時資料且在 20 分鐘內則直接回傳；若先前為模擬資料則嘗試重新抓取真實天氣
                    if (not is_mock_cache) and (datetime.now() - updated_dt < timedelta(minutes=20)):
                        data = json.loads(row["payload_json"])
                        data["cached"] = True
                        return data

        # 1. 先透過 Open-Meteo 即時氣象 API 抓取該地點精確座標的真實即時天氣、36 小時逐時與 7 天預報
        live_data = self._fetch_from_open_meteo(county, town, lat, lng)
        source = "Open-Meteo 即時氣象 API (真實觀測與預報)" if live_data else ""

        # 2. 若使用者有設定 CWA_API_KEY，進一步串接中央氣象署官方預報同步覆蓋縣市摘要
        if Config.has_valid_key(Config.CWA_API_KEY):
            cwa_merged = self._fetch_from_cwa_api(county, town, base_override=live_data)
            if cwa_merged:
                live_data = cwa_merged
                source = "中央氣象署 CWA Open Data API + Open-Meteo 即時預報 (Live)"

        if live_data:
            payload = live_data
        else:
            payload = self._generate_realistic_forecast(county, town)
            source = "離線氣象備援模型 (目前無法連線至外部氣象 API)"

        now_iso = datetime.now().isoformat()
        payload["source"] = source
        payload["updated_at"] = now_iso
        payload["cached"] = False

        with get_db() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO weather_cache
                (location_key, county, town, payload_json, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (loc_key, county, town, json.dumps(payload, ensure_ascii=False), source, now_iso),
            )

        return payload

    def _fetch_from_open_meteo(self, county: str, town: str, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """
        串接 Open-Meteo 即時氣象 API (免 API Key、高精準度、支援全球含台灣各鄉鎮精確經緯度)。
        回傳真實即時氣溫、體感、逐時 36 小時與未來 7 日預報。
        """
        try:
            params = urllib.parse.urlencode({
                "latitude": f"{lat:.4f}",
                "longitude": f"{lng:.4f}",
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
                "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant",
                "wind_speed_unit": "ms",
                "timezone": "Asia/Taipei",
                "forecast_days": 7,
            })
            url = f"https://api.open-meteo.com/v1/forecast?{params}"
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "PersonalLifeDashboard/2.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = json.loads(resp.read().decode("utf-8"))

            cur_raw = raw.get("current", {})
            hourly_raw = raw.get("hourly", {})
            daily_raw = raw.get("daily", {})

            h_times = hourly_raw.get("time", [])
            h_temps = hourly_raw.get("temperature_2m", [])
            h_pops = hourly_raw.get("precipitation_probability", [])
            h_precips = hourly_raw.get("precipitation", [])
            h_codes = hourly_raw.get("weather_code", [])
            h_winds = hourly_raw.get("wind_speed_10m", [])
            h_wdirs = hourly_raw.get("wind_direction_10m", [])

            if not h_times or not daily_raw.get("time"):
                return None

            # 定位目前小時在 hourly 陣列中的索引（以 API 回傳的 current.time 為準，避免本機時鐘偏差）
            cur_time_str = cur_raw.get("time", "")
            cur_hour_prefix = cur_time_str[:13] if len(cur_time_str) >= 13 else datetime.now().strftime("%Y-%m-%dT%H")
            start_idx = 0
            for idx, t_str in enumerate(h_times):
                if t_str[:13] >= cur_hour_prefix:
                    start_idx = idx
                    break

            today_date_str = (cur_time_str[:10] if len(cur_time_str) >= 10 else h_times[start_idx][:10])
            today_dt = datetime.strptime(today_date_str, "%Y-%m-%d").date()
            tomorrow_dt = today_dt + timedelta(days=1)

            hourly_list = []
            for i in range(start_idx, min(len(h_times), start_idx + 36)):
                dt = datetime.strptime(h_times[i], "%Y-%m-%dT%H:%M")
                is_night = dt.hour < 6 or dt.hour >= 18
                cond_text, icon = wmo_code_to_zh(h_codes[i] if i < len(h_codes) else 2, is_night=is_night)
                wind_ms = round(float(h_winds[i] or 0.0), 1)
                beaufort = wind_ms_to_beaufort(wind_ms)
                wind_dir = wind_deg_to_zh(h_wdirs[i] if i < len(h_wdirs) else None)
                pop = int(h_pops[i] or 0) if i < len(h_pops) and h_pops[i] is not None else 0
                rain_mm = round(float(h_precips[i] or 0.0), 1) if i < len(h_precips) and h_precips[i] is not None else 0.0

                if dt.date() == today_dt:
                    date_label = "今日"
                elif dt.date() == tomorrow_dt:
                    date_label = "明日"
                else:
                    date_label = dt.strftime("%m/%d")

                hourly_list.append({
                    "time": dt.strftime("%H:%M"),
                    "date_label": date_label,
                    "full_time": dt.strftime("%Y-%m-%d %H:%M"),
                    "temp": round(float(h_temps[i]), 1),
                    "pop": pop,
                    "rainfall_mm": rain_mm,
                    "wind_speed_ms": wind_ms,
                    "wind_scale": f"{beaufort} 級",
                    "wind_dir": wind_dir,
                    "condition": cond_text,
                    "icon": icon,
                })

            weekdays = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
            d_times = daily_raw.get("time", [])
            d_maxs = daily_raw.get("temperature_2m_max", [])
            d_mins = daily_raw.get("temperature_2m_min", [])
            d_pops = daily_raw.get("precipitation_probability_max", [])
            d_rains = daily_raw.get("precipitation_sum", [])
            d_codes = daily_raw.get("weather_code", [])
            d_winds = daily_raw.get("wind_speed_10m_max", [])
            d_wdirs = daily_raw.get("wind_direction_10m_dominant", [])

            weekly_list = []
            for d in range(min(7, len(d_times))):
                day_dt = datetime.strptime(d_times[d], "%Y-%m-%d")
                cond_text, icon = wmo_code_to_zh(d_codes[d] if d < len(d_codes) else 2, is_night=False)
                wind_ms = round(float(d_winds[d] or 0.0), 1)
                bf = wind_ms_to_beaufort(wind_ms)
                wind_dir = wind_deg_to_zh(d_wdirs[d] if d < len(d_wdirs) else None)
                pop = int(d_pops[d] or 0) if d < len(d_pops) and d_pops[d] is not None else 0
                rain_mm = round(float(d_rains[d] or 0.0), 1) if d < len(d_rains) and d_rains[d] is not None else 0.0

                weekly_list.append({
                    "date": day_dt.strftime("%m/%d"),
                    "day_name": "今日" if d == 0 else ("明日" if d == 1 else weekdays[day_dt.weekday()]),
                    "min_temp": round(float(d_mins[d]), 1),
                    "max_temp": round(float(d_maxs[d]), 1),
                    "pop": pop,
                    "rainfall_mm": rain_mm,
                    "wind_summary": f"{wind_dir} {bf}級 ({wind_ms}m/s)",
                    "wind_dir": wind_dir,
                    "wind_speed_ms": wind_ms,
                    "condition": cond_text,
                    "icon": icon,
                })

            cur_hour = int(cur_time_str[11:13]) if len(cur_time_str) >= 13 else datetime.now().hour
            cur_is_night = cur_hour < 6 or cur_hour >= 18
            cur_cond, cur_icon = wmo_code_to_zh(cur_raw.get("weather_code"), is_night=cur_is_night)
            cur_temp = round(float(cur_raw.get("temperature_2m", hourly_list[0]["temp"])), 1)
            cur_wind_ms = round(float(cur_raw.get("wind_speed_10m", hourly_list[0]["wind_speed_ms"])), 1)
            cur_wind_dir = wind_deg_to_zh(cur_raw.get("wind_direction_10m"))
            cur_bf = wind_ms_to_beaufort(cur_wind_ms)
            cur_pop = hourly_list[0]["pop"] if hourly_list else 0
            cur_rain = round(float(cur_raw.get("precipitation", hourly_list[0]["rainfall_mm"]) or 0.0), 1)
            apparent_t = cur_raw.get("apparent_temperature")
            humidity = cur_raw.get("relative_humidity_2m")

            comfort_str = comfort_label(cur_temp)
            if apparent_t is not None and humidity is not None:
                comfort_str = f"體感 {round(float(apparent_t), 1)}°C • 濕度 {int(humidity)}%"

            return {
                "location": {
                    "county": county,
                    "town": town,
                    "full_name": f"{county}{town}",
                    "lat": lat,
                    "lng": lng,
                },
                "current": {
                    "temp": cur_temp,
                    "min_temp": weekly_list[0]["min_temp"],
                    "max_temp": weekly_list[0]["max_temp"],
                    "pop": cur_pop,
                    "rainfall_mm": cur_rain,
                    "wind_speed_ms": cur_wind_ms,
                    "wind_scale": f"{cur_bf} 級",
                    "wind_dir": cur_wind_dir,
                    "condition": cur_cond,
                    "icon": cur_icon,
                    "comfort": comfort_str,
                },
                "hourly": hourly_list,
                "weekly": weekly_list,
            }
        except Exception:
            return None

    def _fetch_from_cwa_api(self, county: str, town: str, base_override: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        串接中央氣象署開放資料平台 API (F-C0032-001 縣市預報)
        若金鑰無效或無網路則安全回傳 None。
        """
        try:
            params = urllib.parse.urlencode({
                "Authorization": Config.CWA_API_KEY,
                "locationName": county,
                "format": "JSON",
            })
            url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?{params}"
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "PersonalLifeDashboard/2.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                if raw.get("success") == "true":
                    base = base_override or self._generate_realistic_forecast(county, town)
                    records = raw.get("records", {}).get("location", [])
                    if records:
                        elements = {el["elementName"]: el["time"] for el in records[0].get("weatherElement", [])}
                        if "MinT" in elements and "MaxT" in elements:
                            min_t = int(elements["MinT"][0]["parameter"]["parameterName"])
                            max_t = int(elements["MaxT"][0]["parameter"]["parameterName"])
                            base["weekly"][0]["min_temp"] = min_t
                            base["weekly"][0]["max_temp"] = max_t
                            base["current"]["min_temp"] = min_t
                            base["current"]["max_temp"] = max_t
                        if "PoP" in elements:
                            pop = int(elements["PoP"][0]["parameter"]["parameterName"])
                            base["current"]["pop"] = pop
                            base["weekly"][0]["pop"] = pop
                        if "Wx" in elements:
                            wx = elements["Wx"][0]["parameter"]["parameterName"]
                            base["current"]["condition"] = wx
                            base["weekly"][0]["condition"] = wx
                    return base
        except Exception:
            return None
        return None

    def _generate_realistic_forecast(self, county: str, town: str) -> Dict[str, Any]:
        """完全離線時的備援氣象模型（僅在外部即時氣象 API 無法連線時使用）。"""
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        seed_int = int(hashlib.md5(f"{county}_{town}_{now.strftime('%Y-%m-%d')}".encode()).hexdigest()[:8], 16)

        base_temp = 21
        wind_boost = 0.0
        rain_bias = 0
        if "新竹" in county:
            wind_boost = 2.2
            base_temp = 21
        elif county in ("臺南市", "高雄市"):
            base_temp = 25
            rain_bias = -10
        elif county in ("宜蘭縣", "花蓮縣"):
            rain_bias = 15
            base_temp = 20

        hourly_list = []
        for h in range(36):
            dt = now + timedelta(hours=h)
            hour_of_day = dt.hour
            diurnal = math.sin((hour_of_day - 8) * math.pi / 12) * 3.8
            loc_offset = ((seed_int + h * 7) % 5 - 2) * 0.3
            temp = round(base_temp + diurnal + loc_offset, 1)

            wave = math.sin((h + (seed_int % 12)) * 0.35) * 20
            pop = max(5, min(90, int((25 + wave + rain_bias) // 5 * 5)))
            rainfall_mm = round((pop / 100.0) * 3.2, 1) if pop >= 35 else 0.0

            wind_speed = round(max(1.5, 3.0 + wind_boost + math.sin(h * 0.4) * 1.6), 1)
            wind_dir = WIND_DIRECTIONS[(seed_int + h // 4) % len(WIND_DIRECTIONS)]
            beaufort = wind_ms_to_beaufort(wind_speed)

            cond = next(c for c in WEATHER_CONDITIONS if pop <= c["pop_max"])
            is_night = hour_of_day < 6 or hour_of_day >= 18
            icon = "🌙" if (is_night and pop <= 20) else cond["icon"]

            hourly_list.append({
                "time": dt.strftime("%H:%M"),
                "date_label": "今日" if dt.date() == now.date() else ("明日" if dt.date() == (now + timedelta(days=1)).date() else dt.strftime("%m/%d")),
                "full_time": dt.strftime("%Y-%m-%d %H:%M"),
                "temp": temp,
                "pop": pop,
                "rainfall_mm": rainfall_mm,
                "wind_speed_ms": wind_speed,
                "wind_scale": f"{beaufort} 級",
                "wind_dir": wind_dir,
                "condition": cond["desc"],
                "icon": icon,
            })

        weekdays = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
        weekly_list = []
        for d in range(7):
            day_dt = now + timedelta(days=d)
            day_seed = (seed_int + d * 31) % 100
            min_t = round(base_temp - 3.5 + ((day_seed % 5) - 2) * 0.6, 1)
            max_t = round(base_temp + 4.2 + ((day_seed % 7) - 3) * 0.6, 1)
            pop = max(10, min(85, int((20 + (day_seed % 55) + rain_bias) // 10 * 10)))
            rainfall_mm = round((pop / 100.0) * 12.5, 1) if pop >= 30 else 0.0
            wind_ms = round(2.8 + wind_boost + ((day_seed % 4) * 0.5), 1)
            bf = wind_ms_to_beaufort(wind_ms)
            wind_dir = WIND_DIRECTIONS[(seed_int + d) % len(WIND_DIRECTIONS)]
            cond = next(c for c in WEATHER_CONDITIONS if pop <= c["pop_max"])

            weekly_list.append({
                "date": day_dt.strftime("%m/%d"),
                "day_name": "今日" if d == 0 else ("明日" if d == 1 else weekdays[day_dt.weekday()]),
                "min_temp": min_t,
                "max_temp": max_t,
                "pop": pop,
                "rainfall_mm": rainfall_mm,
                "wind_summary": f"{wind_dir} {bf}級 ({wind_ms}m/s)",
                "wind_dir": wind_dir,
                "wind_speed_ms": wind_ms,
                "condition": cond["desc"],
                "icon": cond["icon"],
            })

        current = hourly_list[0]
        return {
            "location": {
                "county": county,
                "town": town,
                "full_name": f"{county}{town}",
            },
            "current": {
                "temp": current["temp"],
                "min_temp": weekly_list[0]["min_temp"],
                "max_temp": weekly_list[0]["max_temp"],
                "pop": current["pop"],
                "rainfall_mm": current["rainfall_mm"],
                "wind_speed_ms": current["wind_speed_ms"],
                "wind_scale": current["wind_scale"],
                "wind_dir": current["wind_dir"],
                "condition": current["condition"],
                "icon": current["icon"],
                "comfort": comfort_label(current["temp"]),
            },
            "hourly": hourly_list,
            "weekly": weekly_list,
        }

    def on_cron_tick(self, now_dt: datetime) -> None:
        if now_dt.hour == 6 and now_dt.minute == 0:
            self.get_forecast(force_refresh=True)


weather_module = WeatherModule()
