#!/usr/bin/env python3
# send_weather.py — Includes Tehran Air Quality (Park Shahr) via air.tehran.ir API

import os
import requests
import datetime
import jdatetime

# ---------- settings ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
VISUALCROSSING_KEY = os.environ.get("VISUALCROSSING_KEY")

CHAT_IDS = os.environ.get("CHAT_IDS", "")
REGION_NAME = os.environ.get("REGION_NAME", "پانزده خرداد")
IMAGE_URL = os.environ.get("IMAGE_URL", "")

LAT = os.environ.get("LAT", "35.6764")
LON = os.environ.get("LON", "51.4181")
UNITS = os.environ.get("UNITS", "metric")

if not TELEGRAM_TOKEN or not VISUALCROSSING_KEY:
    raise SystemExit("Error: TELEGRAM_TOKEN and VISUALCROSSING_KEY are required.")

# ---------- translations ----------
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

# ---------- AQI status ----------
def get_aqi_status(aqi_value):
    if aqi_value in (None, "—"):
        return "⚪️ نامشخص"
    try:
        aqi = int(aqi_value)
    except Exception:
        return "⚪️ نامشخص"
    if aqi <= 50: return "🟢 پاک"
    if aqi <= 100: return "🟡 قابل قبول"
    if aqi <= 150: return "🟠 ناسالم برای حساس‌ها"
    if aqi <= 200: return "🔴 ناسالم"
    if aqi <= 300: return "🟣 بسیار ناسالم"
    return "🟤 خطرناک"

# ---------- LTR isolation ----------
RLI = "\u2067"
PDI = "\u2069"
ZWNJ = "\u200c"

def ltr(s: str) -> str:
    return f"{RLI}{s}{PDI}"

# ---------- fetch weather ----------
def fetch_weather_data(lat, lon):
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}"
    params = {"unitGroup": UNITS, "key": VISUALCROSSING_KEY, "contentType": "json", "include": "current,hours,days"}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# ---------- fetch AQI from Tehran Air ----------
def fetch_tehran_aqi(station_name="پارک شهر"):
    """
    Uses air.tehran.ir official API:
    https://air.tehran.ir/api/Station/GetStationAQI
    """
    try:
        url = "https://air.tehran.ir/api/Station/GetStationAQI"
        r = requests.post(url, json={"Station": station_name}, timeout=15)
        r.raise_for_status()
        data = r.json()

        result = data.get("Result")
        if result and "AQI" in result:
            return result["AQI"]

    except Exception:
        pass

    return "—"

# ---------- format message ----------
def format_message(region_name, weather_json, aqi_value):
    now_utc = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    j_now = jdatetime.datetime.fromgregorian(datetime=now_utc)
    date_fa = j_now.strftime("%Y/%m/%d")

    current = weather_json.get("currentConditions", {}) or {}
    desc = WEATHER_TRANSLATIONS.get(current.get("icon", "default"), WEATHER_TRANSLATIONS["default"])

    temp_current = round(current.get("temp", 0), 1)
    humidity = current.get("humidity", "—")
    pop = int(current.get("precipprob", 0)) if current.get("precipprob") is not None else 0

    temp_current_s = ltr(f"{temp_current}°C")
    humidity_s = ltr(f"{humidity}%")
    pop_s = ltr(f"{pop}%")

    hours = []
    for d in weather_json.get("days", []):
        hours.extend(d.get("hours", []))

    start_utc = datetime.datetime.utcnow()
    end_utc = start_utc + datetime.timedelta(hours=24)
    temps_24h = []

    for h in hours:
        try:
            ts = datetime.datetime.utcfromtimestamp(h.get("datetimeEpoch"))
        except Exception:
            continue
        if start_utc <= ts <= end_utc:
            temps_24h.append(h.get("temp"))

    if temps_24h:
        t_min_s = ltr(f"{round(min(temps_24h), 1)}°C")
        t_max_s = ltr(f"{round(max(temps_24h), 1)}°C")
    else:
        t_min_s = t_max_s = "—"

    forecast_lines = []
    first_future = next((i for i, h in enumerate(hours)
                         if datetime.datetime.utcfromtimestamp(h.get("datetimeEpoch")) > start_utc), 0)

    for i in range(4):
        idx = first_future + i * 3
        if idx >= len(hours):
            break
        h = hours[idx]
        try:
            ts = datetime.datetime.utcfromtimestamp(h.get("datetimeEpoch")) + datetime.timedelta(hours=3.5)
        except Exception:
            continue

        time_str = jdatetime.datetime.fromgregorian(datetime=ts).strftime("%H:%M")
        w_fa = WEATHER_TRANSLATIONS.get(h.get("icon", "default"), "؟")

        t_f = round(h.get("temp", 0), 1)
        p_f = int(h.get("precipprob", 0)) if h.get("precipprob") is not None else 0

        t_f_s = ltr(f"{t_f}°C")
        p_f_s = ltr(f"{p_f}%")

        line = f"🕒 {time_str} | {w_fa} | 🌡 {t_f_s} | ☔ {p_f_s}{ZWNJ} احتمال بارش"
        forecast_lines.append(line)

    aqi_text = get_aqi_status(aqi_value)

    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n"
        f"📍 منطقه: {region_name}\n"
        f"📅 تاریخ: {date_fa}\n"
        f"وضعیت: {desc}\n"
        f"دمای فعلی: {temp_current_s}\n"
        f"رطوبت: {humidity_s}\n"
        f"احتمال بارش فعلی: {pop_s}\n"
        f"حداقل: {t_min_s} | حداکثر: {t_max_s}\n"
        f"کیفیت هوا: {ltr(str(aqi_value))} ({aqi_text})\n\n"
        f"<b>پیش‌بینی ۱۲ ساعت آینده:</b>\n"
        + "\n".join(forecast_lines)
    )

    return msg

# ---------- send ----------
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
        print("Telegram send error:", e)

# ---------- main ----------
def main():
    lat, lon = float(LAT), float(LON)
    weather = fetch_weather_data(lat, lon)
    aqi = fetch_tehran_aqi("پارک شهر")
    msg = format_message(REGION_NAME, weather, aqi)

    for cid in [c.strip() for c in CHAT_IDS.split(",") if c.strip()]:
        send_to_telegram(cid, msg)

if __name__ == "__main__":
    main()
