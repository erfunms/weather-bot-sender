#!/usr/bin/env python3
# send_weather.py
import os
import requests
import datetime
import time

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY")
CHAT_IDS = os.environ.get("CHAT_IDS", "")
REGION_NAME = os.environ.get("REGION_NAME", "پانزده خرداد")
IMAGE_URL = os.environ.get("IMAGE_URL", "")
LAT = os.environ.get("LAT")
LON = os.environ.get("LON")
UNITS = os.environ.get("UNITS", "metric")

if not TELEGRAM_TOKEN or not OPENWEATHER_KEY:
    raise SystemExit("Please set TELEGRAM_TOKEN and OPENWEATHER_KEY as environment variables.")

# --- ترجمه‌ی وضعیت جوی به فارسی ---
def translate_weather(desc_en):
    desc_en = desc_en.lower()
    mapping = {
        "clear": "☀️ صاف",
        "clouds": "☁️ ابری",
        "few clouds": "🌤 کمی ابری",
        "scattered clouds": "🌥 ابرهای پراکنده",
        "broken clouds": "☁️ نیمه‌ابری",
        "shower rain": "🌦 رگبار باران",
        "rain": "🌧 بارانی",
        "thunderstorm": "⛈ طوفانی",
        "snow": "❄️ برفی",
        "mist": "🌫 مه‌آلود",
        "haze": "🌫 مه‌آلود",
        "fog": "🌫 مه",
    }
    for k, v in mapping.items():
        if k in desc_en:
            return v
    return desc_en.capitalize()

# --- کیفیت هوا به صورت توصیفی ---
def describe_aqi(aqi):
    aqi = int(aqi)
    if aqi == 1:
        return "🟢 بسیار پاک"
    elif aqi == 2:
        return "🟢 پاک"
    elif aqi == 3:
        return "🟡 نسبتاً آلوده"
    elif aqi == 4:
        return "🟠 آلوده"
    elif aqi == 5:
        return "🔴 بسیار آلوده"
    else:
        return "نامشخص"

# --- توابع دریافت داده‌ها ---
def geocode_place(place_name):
    url = f"http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": place_name, "limit": 1, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError("Geocoding failed, no results for place: " + place_name)
    return float(data[0]["lat"]), float(data[0]["lon"])

def fetch_current_weather(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "units": UNITS, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_forecast(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "units": UNITS, "appid": OPENWEATHER_KEY, "cnt": 8}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_air_pollution(lat, lon):
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# --- قالب پیام فارسی ---
def format_message(region_name, current_json, forecast_json, air_json):
    now = datetime.datetime.utcnow() + datetime.timedelta()
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")

    current = current_json
    desc_en = current.get("weather", [{}])[0].get("description", "—")
    desc = translate_weather(desc_en)
    temp = current.get("main", {}).get("temp", "—")
    humidity = current.get("main", {}).get("humidity", "—")
    temp_min = current.get("main", {}).get("temp_min", "—")
    temp_max = current.get("main", {}).get("temp_max", "—")
    pop = forecast_json.get("list", [{}])[0].get("pop", 0) * 100 if forecast_json.get("list") else 0

    # Air quality
    aq = air_json.get("list", [{}])[0] if air_json else {}
    aqi_val = aq.get("main", {}).get("aqi", "—")
    aqi_text = describe_aqi(aqi_val)
    components = aq.get("components", {})

    # Forecast (12 hours = 4 * 3h)
    hourly = forecast_json.get("list", [])[:4]
    forecast_lines = []
    for h in hourly:
        ts = datetime.datetime.utcfromtimestamp(h["dt"])
        time_str = ts.strftime("%H:%M")
        w = translate_weather(h.get("weather", [{}])[0].get("description", ""))
        t = h.get("main", {}).get("temp", "—")
        p = int(h.get("pop", 0) * 100)
        forecast_lines.append(f"🕒 {time_str} → {w} | 🌡 {t}° | 💧 احتمال بارش: {p}%")

    forecast_text = "\n".join(forecast_lines)

    msg = (
        f"🌤 <b>وضعیت آب‌وهوای امروز</b>\n\n"
        f"📍 <b>منطقه:</b> {region_name}\n"
        f"📅 <b>تاریخ:</b> {now_str}\n\n"
        f"🌦 <b>وضعیت جوی:</b> {desc}\n"
        f"🌡 <b>دمای فعلی:</b> {temp}°C\n"
        f"💧 <b>رطوبت هوا:</b> {humidity}%\n"
        f"🌧 <b>احتمال بارش:</b> {int(pop)}%\n"
        f"🌡 <b>حداقل دما:</b> {temp_min}°C\n"
        f"🌡 <b>حداکثر دما:</b> {temp_max}°C\n\n"
        f"🕒 <b>پیش‌بینی ۱۲ ساعت آینده:</b>\n{forecast_text}\n\n"
        f"🌫 <b>شاخص کیفیت هوا:</b> {aqi_val} ({aqi_text})\n"
    )

    if components:
        comp_summary = ", ".join(
            [f"{k}:{int(v)}" for k, v in components.items() if v is not None][:5]
        )
        msg += f"💨 <b>جزئیات آلودگی:</b> {comp_summary}\n"

    msg += "\n📸 تصویر: نمای منطقه پانزده خرداد"
    return msg

# --- ارسال پیام / عکس ---
def send_photo(chat_id, photo_url, caption_html):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": chat_id, "caption": caption_html, "parse_mode": "HTML", "photo": photo_url}
    r = requests.post(send_url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()

def send_message(chat_id, text_html):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text_html, "parse_mode": "HTML"}
    r = requests.post(send_url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()

# --- main ---
def main():
    global LAT, LON
    if not LAT or not LON:
        lat, lon = geocode_place(REGION_NAME)
        LAT, LON = str(lat), str(lon)

    latf, lonf = float(LAT), float(LON)
    current_weather = fetch_current_weather(latf, lonf)
    forecast = fetch_forecast(latf, lonf)
    air = fetch_air_pollution(latf, lonf)
    caption = format_message(REGION_NAME, current_weather, forecast, air)

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        raise SystemExit("No CHAT_IDS set.")

    for cid in chat_ids:
        try:
            if IMAGE_URL:
                send_photo(cid, IMAGE_URL, caption)
            else:
                send_message(cid, caption)
            time.sleep(1)
        except Exception as e:
            print(f"Failed to send to {cid}: {e}")

if __name__ == "__main__":
    main()
