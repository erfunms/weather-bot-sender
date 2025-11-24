#!/usr/bin/env python3
# send_weather.py (Stable RTL Edition + Perfect Forecast Formatting)

import os
import requests
import datetime
import time
import jdatetime

# --- تنظیمات ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
VISUALCROSSING_KEY = os.environ.get("VISUALCROSSING_KEY")
IQAIR_KEY = os.environ.get("IQAIR_KEY")
CHAT_IDS = os.environ.get("CHAT_IDS", "")
REGION_NAME = os.environ.get("REGION_NAME", "تهران")
IMAGE_URL = os.environ.get("IMAGE_URL", "")
LAT = os.environ.get("LAT", "35.6892")
LON = os.environ.get("LON", "51.3890")
UNITS = os.environ.get("UNITS", "metric")

# --- کاراکترهای کنترل Unicode ---
LRM = "\u200E"   # Left-to-Right Mark
RLE = "\u202B"   # Right-to-Left Embedding
PDF = "\u202C"   # Pop Directional Formatting
EN = "\u2002"    # En Space

if not TELEGRAM_TOKEN or not VISUALCROSSING_KEY or not IQAIR_KEY:
    raise SystemExit("Error: Missing required environment variables.")

# --- ترجمه وضعیت هوا ---
WEATHER_TRANSLATIONS = {
    "clear-day": "آسمان صاف ☀️", "clear-night": "آسمان صاف 🌙",
    "cloudy": "ابری ☁️", "partly-cloudy-day": "نیمه‌ابری 🌤️",
    "partly-cloudy-night": "نیمه‌ابری ☁️", "rain": "باران 🌧️",
    "snow": "برف ❄️", "wind": "بادی 🌬️", "fog": "مه 🌫️",
    "sleet": "باران و برف 🌨️", "hail": "تگرگ 🧊",
    "thunderstorm": "رعد و برق ⛈️", "default": "نامشخص ❓"
}

# --- اصلاح جهت متن ---
def fix_text(x):
    return f"{LRM}{x}{LRM}"

# --- API هوا ---
def fetch_weather_data(lat, lon):
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}"
    params = {
        "unitGroup": UNITS,
        "key": VISUALCROSSING_KEY,
        "contentType": "json",
        "include": "current,hours,days"
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# --- API آلودگی هوا ---
def fetch_air_pollution(lat, lon):
    url = "http://api.airvisual.com/v2/nearest_city"
    params = {"lat": lat, "lon": lon, "key": IQAIR_KEY}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "success":
            return data["data"]["current"]["pollution"]["aqius"]
    except:
        pass
    return "—"

# --- ساخت پیام ---
def format_message(region_name, weather_json, aqi_value):

    # زمان فارسی
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    jnow = jdatetime.datetime.fromgregorian(datetime=now)
    date_fa = jnow.strftime("%Y/%m/%d")

    # داده فعلی
    curr = weather_json.get("currentConditions", {})
    desc = WEATHER_TRANSLATIONS.get(curr.get("icon", "default"), "نامشخص")
    temp_now = fix_text(f"{round(curr.get('temp', 0), 1)}°C")

    # محاسبه کمینه/بیشینه ۲۴ ساعت
    hours = []
    for d in weather_json.get("days", []):
        hours.extend(d.get("hours", []))

    start = datetime.datetime.utcnow()
    end = start + datetime.timedelta(hours=24)

    temps = [
        h.get("temp")
        for h in hours
        if start <= datetime.datetime.utcfromtimestamp(h["datetimeEpoch"]) <= end
    ]

    t_min = fix_text(f"{round(min(temps), 1)}°C") if temps else "—"
    t_max = fix_text(f"{round(max(temps), 1)}°C") if temps else "—"

    # --- پیش‌بینی هر ۳ ساعت ---
    forecast_lines = []

    start_idx = 0
    for i, h in enumerate(hours):
        if datetime.datetime.utcfromtimestamp(h["datetimeEpoch"]) > start:
            start_idx = i
            break

    for step in range(8):  # 8 دوره سه‌ساعته
        idx = start_idx + step * 3
        if idx >= len(hours):
            break

        h = hours[idx]

        ts = datetime.datetime.utcfromtimestamp(h["datetimeEpoch"]) + datetime.timedelta(hours=3.5)
        time_fa = jdatetime.datetime.fromgregorian(datetime=ts).strftime("%H:%M")
        cond = WEATHER_TRANSLATIONS.get(h.get("icon", "default"), "؟")

        temp_f = fix_text(f"{round(h.get('temp', 0), 1)}°C")
        rain_f = fix_text(f"{int(h.get('precipprob', 0))}%")

        # ⬅️ نسخه کاملاً پایدار بدون قاطی‌شدن
        line = (
            f"{RLE}"
            f"🕒 {time_fa}{EN}"
            f"{cond}{EN}"
            f"🌡 {temp_f}{EN}"
            f"☔ {rain_f} احتمال بارش"
            f"{PDF}"
        )

        forecast_lines.append(line)

    # --- پیام نهایی ---
    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n"
        f"📍 منطقه: {region_name}\n"
        f"📅 تاریخ: {date_fa}\n"
        f"وضعیت: {desc}\n"
        f"دمای فعلی: {temp_now}\n"
        f"حداقل: {t_min}{EN}|{EN}حداکثر: {t_max}\n"
        f"کیفیت هوا: {aqi_value} ({get_aqi_status(aqi_value)})\n\n"
        f"<b>پیش‌بینی ۲۴ ساعت آینده:</b>\n" + "\n".join(forecast_lines)
    )

    return msg

# --- ارسال ---
def main():
    lat, lon = float(LAT), float(LON)
    wd = fetch_weather_data(lat, lon)
    aqi = fetch_air_pollution(lat, lon)
    msg = format_message(REGION_NAME, wd, aqi)

    for cid in [c.strip() for c in CHAT_IDS.split(",") if c.strip()]:
        try:
            if IMAGE_URL:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                data = {"chat_id": cid, "caption": msg, "photo": IMAGE_URL, "parse_mode": "HTML"}
            else:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                data = {"chat_id": cid, "text": msg, "parse_mode": "HTML"}

            requests.post(url, data=data, timeout=20)

        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    main()
