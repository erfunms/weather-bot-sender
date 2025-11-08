#!/usr/bin/env python3
# send_weather.py

import os
import requests
import datetime
import time
import jdatetime

# --- تنظیمات اصلی ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY")
AQICN_TOKEN = os.environ.get("AQICN_TOKEN")
CHAT_IDS = os.environ.get("CHAT_IDS", "")
REGION_NAME = os.environ.get("REGION_NAME", "پانزده خرداد")
IMAGE_URL = os.environ.get("IMAGE_URL", "")
LAT = os.environ.get("LAT")
LON = os.environ.get("LON")
UNITS = os.environ.get("UNITS", "metric")

if not TELEGRAM_TOKEN or not OPENWEATHER_KEY or not AQICN_TOKEN:
    raise SystemExit("⚠️ لطفاً تمام مقادیر لازم (TELEGRAM_TOKEN, OPENWEATHER_KEY, AQICN_TOKEN) را تنظیم کنید.")

# --- دیکشنری‌ها ---
WEATHER_TRANSLATIONS = {
    "clear sky": "آسمان صاف ☀️", "few clouds": "کمی ابری 🌤️",
    "scattered clouds": "تکه‌ابرهای پراکنده 🌥️", "broken clouds": "ابرهای متراکم ☁️",
    "shower rain": "بارندگی رگباری 🌧️", "rain": "باران 🌧️",
    "thunderstorm": "رعد و برق ⛈️", "snow": "برف ❄️",
    "mist": "مه یا غبار 🌫️", "overcast clouds": "آسمان ابری ☁️",
}

# --- مقیاس‌های AQI ---
def get_aqi_status(aqi_value):
    if aqi_value is None or aqi_value == "—":
        return "⚪️ نامشخص"
    try:
        aqi = int(aqi_value)
    except ValueError:
        return "⚪️ نامشخص"
    if aqi <= 50:
        return "🟢 پاک — کیفیت هوا رضایت‌بخش است."
    elif aqi <= 100:
        return "🟡 قابل قبول — احتیاط برای افراد حساس."
    elif aqi <= 150:
        return "🟠 ناسالم برای گروه‌های حساس — فعالیت‌های طولانی‌مدت را محدود کنید."
    elif aqi <= 200:
        return "🔴 ناسالم — همه ممکن است اثرات بهداشتی را تجربه کنند."
    elif aqi <= 300:
        return "🟣 بسیار ناسالم — هشدار سلامت: خطرناک برای عموم."
    else:
        return "🟤 خطرناک — وضعیت اضطراری سلامت."

# --- دریافت داده‌ها ---
def geocode_place(place_name):
    url = f"http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": place_name, "limit": 1, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError("❌ مکان موردنظر پیدا نشد: " + place_name)
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
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
    params = {"token": AQICN_TOKEN}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("status") == "ok" and data.get("data") and data["data"].get("aqi"):
        return data["data"]["aqi"]
    return "—"

# --- قالب پیام نهایی ---
def format_message(region_name, current_json, forecast_json, aqi_value):
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    date_fa = j_now.strftime("%Y/%m/%d")
    time_fa = j_now.strftime("%H:%M")

    current = current_json
    desc = current.get("weather", [{}])[0].get("description", "—")
    desc_fa = WEATHER_TRANSLATIONS.get(desc, desc)
    temp = round(current.get("main", {}).get("temp", 0), 1)
    humidity = current.get("main", {}).get("humidity", "—")

    temps = [i["main"]["temp"] for i in forecast_json.get("list", [])[:8] if "main" in i]
    temp_min = round(min(temps), 1) if temps else "—"
    temp_max = round(max(temps), 1) if temps else "—"

    pop = int(forecast_json.get("list", [{}])[0].get("pop", 0) * 100)
    aqi = str(aqi_value)
    aqi_text = get_aqi_status(aqi_value)

    forecast_lines = []
    for h in forecast_json.get("list", [])[:4]:
        ts = datetime.datetime.utcfromtimestamp(h["dt"]) + datetime.timedelta(hours=3.5)
        j_ts = jdatetime.datetime.fromgregorian(datetime=ts)
        time_str = j_ts.strftime("%H:%M")
        w = h.get("weather", [{}])[0].get("description", "")
        w_fa = WEATHER_TRANSLATIONS.get(w, w)
        t = round(h.get("main", {}).get("temp", 0), 1)
        p = int(h.get("pop", 0) * 100)
        forecast_lines.append(f"🕒 {time_str} | {w_fa} | 🌡️ {t}° | ☔ {p}% احتمال بارش")

    forecast_text = "\n".join(forecast_lines)

    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n"
        f"📍 منطقه: {region_name}\n"
        f"📅 تاریخ: {date_fa}\n"
        f"⏰ ساعت: {time_fa}\n\n"
        f"وضعیت جوی: {desc_fa}\n"
        f"دمای فعلی: {temp}°C\n"
        f"رطوبت: {humidity}%\n"
        f"احتمال بارش: {pop}%\n"
        f"حداقل دما: {temp_min}°C\n"
        f"حداکثر دما: {temp_max}°C\n"
        f"شاخص کیفیت هوا ({aqi}): {aqi_text}\n\n"
        f"<b>🔮 پیش‌بینی ۱۲ ساعت آینده:</b>\n{forecast_text}"
    )
    return msg

# --- توابع ارسال ---
def send_photo(chat_id, photo_url, caption_html):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": chat_id, "caption": caption_html, "parse_mode": "HTML", "photo": photo_url}
    r = requests.post(url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()

def send_message(chat_id, text_html):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text_html, "parse_mode": "HTML"}
    r = requests.post(url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()

# --- اجرای اصلی ---
def main():
    global LAT, LON
    if not LAT or not LON:
        try:
            lat, lon = geocode_place(REGION_NAME)
            LAT, LON = str(lat), str(lon)
        except Exception as e:
            raise SystemExit(f"❌ خطا در موقعیت‌یابی: {e}")

    latf, lonf = float(LAT), float(LON)
    current_weather = fetch_current_weather(latf, lonf)
    forecast = fetch_forecast(latf, lonf)
    aqi_value = fetch_air_pollution(latf, lonf)
    caption = format_message(REGION_NAME, current_weather, forecast, aqi_value)

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        raise SystemExit("⚠️ لطفاً CHAT_IDS را تنظیم کنید.")

    for cid in chat_ids:
        try:
            if IMAGE_URL:
                send_photo(cid, IMAGE_URL, caption)
            else:
                send_message(cid, caption)
            time.sleep(1)
        except Exception as e:
            print(f"❌ ارسال پیام به {cid} ناموفق بود: {e}")

if __name__ == "__main__":
    main()
