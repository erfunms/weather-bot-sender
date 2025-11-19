#!/usr/bin/env python3
# send_weather.py — Final Clean Version (Full Fix + LRM Support)

import os
import requests
import datetime
import jdatetime

# ----------------------------- تنظیمات -----------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
VISUALCROSSING_KEY = os.environ.get("VISUALCROSSING_KEY")
AQICN_TOKEN = os.environ.get("AQICN_TOKEN")

CHAT_IDS = os.environ.get("CHAT_IDS", "")
REGION_NAME = os.environ.get("REGION_NAME", "پانزده خرداد")
IMAGE_URL = os.environ.get("IMAGE_URL", "")

LAT = os.environ.get("LAT", "35.6764")
LON = os.environ.get("LON", "51.4181")
UNITS = os.environ.get("UNITS", "metric")

if not TELEGRAM_TOKEN or not VISUALCROSSING_KEY or not AQICN_TOKEN:
    raise SystemExit("Error: Missing Environment Variables.")

# ----------------------------- دیکشنری آب‌وهوا -----------------------------
WEATHER_TRANSLATIONS = {
    "clear-day": "آسمان صاف ☀️",
    "clear-night": "آسمان صاف 🌙",
    "cloudy": "ابری ☁️",
    "partly-cloudy-day": "نیمه‌ابری 🌤️",
    "partly-cloudy-night": "نیمه‌ابری ☁️",
    "rain": "بارانی 🌧️",
    "snow": "برفی ❄️",
    "wind": "بادی 🌬️",
    "fog": "مه‌آلود 🌫️",
    "sleet": "باران و برف 🌨️",
    "hail": "تگرگ 🧊",
    "thunderstorm": "رعدوبرق ⛈️",
    "default": "نامشخص ❓",
}

# ----------------------------- AQI -----------------------------
def get_aqi_status(aqi_value):
    if aqi_value in (None, "—"):
        return "⚪️ نامشخص"
    try:
        aqi = int(aqi_value)
    except ValueError:
        return "⚪️ نامشخص"

    if aqi <= 50: return "🟢 پاک"
    if aqi <= 100: return "🟡 قابل قبول"
    if aqi <= 150: return "🟠 ناسالم برای حساس‌ها"
    if aqi <= 200: return "🔴 ناسالم"
    if aqi <= 300: return "🟣 بسیار ناسالم"
    return "🟤 خطرناک"

# ----------------------------- LRM -----------------------------
def fix_text(text):
    """افزودن LRM دوطرف متن برای جلوگیری از به‌هم‌ریختگی"""
    LRM = "\u200E"
    return f"{LRM}{text}{LRM}"

# ----------------------------- API Weather -----------------------------
def fetch_weather_data(lat, lon):
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}"
    params = {
        "unitGroup": UNITS,
        "key": VISUALCROSSING_KEY,
        "contentType": "json",
        "include": "current,hours,days",
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# ----------------------------- API AQI -----------------------------
def fetch_air_pollution(lat, lon):
    url = "https://api.waqi.info/feed/tehran/"
    params = {"token": AQICN_TOKEN}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "ok":
            return data["data"].get("aqi", "—")
    except:
        pass
    return "—"

# ----------------------------- ساخت پیام -----------------------------
def format_message(region_name, weather_json, aqi_value):

    # تبدیل زمان
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    date_fa = j_now.strftime("%Y/%m/%d")

    # وضعیت فعلی
    current = weather_json.get("currentConditions", {})
    desc = WEATHER_TRANSLATIONS.get(current.get("icon"), "نامشخص")

    # دمای فعلی با LRM
    temp_val = round(current.get("temp", 0), 1)
    temp_str = fix_text(f"{temp_val}°C")

    # ۲۴ ساعت آینده
    hours = []
    for d in weather_json.get("days", []):
        hours.extend(d.get("hours", []))

    start = datetime.datetime.utcnow()
    end = start + datetime.timedelta(hours=24)

    temps_24h = [
        h.get("temp") for h in hours
        if start <= datetime.datetime.utcfromtimestamp(h.get("datetimeEpoch")) <= end
    ]

    t_min = fix_text(f"{round(min(temps_24h), 1)}°C") if temps_24h else "—"
    t_max = fix_text(f"{round(max(temps_24h), 1)}°C") if temps_24h else "—"

    # ---------------- پیش‌بینی ۴ بازه ۳ ساعته ----------------
    forecast_lines = []

    first_future = next(
        (i for i, h in enumerate(hours)
         if datetime.datetime.utcfromtimestamp(h["datetimeEpoch"]) > start),
        0
    )

    for i in range(4):
        idx = first_future + i * 3
        if idx >= len(hours):
            break

        h = hours[idx]
        ts = datetime.datetime.utcfromtimestamp(h["datetimeEpoch"]) + datetime.timedelta(hours=3.5)
        time_str = jdatetime.datetime.fromgregorian(datetime=ts).strftime("%H:%M")

        w_fa = WEATHER_TRANSLATIONS.get(h.get("icon"), "؟")

        t_f = fix_text(f"{round(h.get('temp', 0), 1)}°C")
        r_f = fix_text(f"{int(h.get('precipprob', 0))}%")

        forecast_lines.append(
            f"🕒 {time_str} | {w_fa} | 🌡 {t_f} | ☔ {r_f} بارش"
        )

    # ---------------- پیام نهایی ----------------
    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n"
        f"📍 منطقه: {region_name}\n"
        f"📅 تاریخ: {date_fa}\n"
        f"وضعیت: {desc}\n"
        f"دمای فعلی: {temp_str}\n"
        f"حداقل: {t_min} | حداکثر: {t_max}\n"
        f"کیفیت هوا: {aqi_value} ({get_aqi_status(aqi_value)})\n\n"
        f"<b>پیش‌بینی ۱۲ ساعت آینده:</b>\n" +
        "\n".join(forecast_lines)
    )

    return msg

# ----------------------------- ارسال به تلگرام -----------------------------
def send_to_telegram(chat_id, msg):
    if IMAGE_URL:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        data = {"chat_id": chat_id, "caption": msg, "photo": IMAGE_URL, "parse_mode": "HTML"}
    else:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}

    try:
        requests.post(url, data=data, timeout=20)
    except Exception as e:
        print(f"[Error Telegram] {e}")

# ----------------------------- MAIN -----------------------------
def main():
    lat, lon = float(LAT), float(LON)

    weather = fetch_weather_data(lat, lon)
    aqi = fetch_air_pollution(lat, lon)

    msg = format_message(REGION_NAME, weather, aqi)

    for cid in [c.strip() for c in CHAT_IDS.split(",") if c.strip()]:
        send_to_telegram(cid, msg)

if __name__ == "__main__":
    main()
