#!/usr/bin/env python3
# send_weather.py

import os
import requests
import datetime
import time
import jdatetime # برای تاریخ شمسی (باید در Action نصب شود)

# --- تنظیمات اصلی ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY")
CHAT_IDS = os.environ.get("CHAT_IDS", "")
REGION_NAME = os.environ.get("REGION_NAME", "پانزده خرداد")
IMAGE_URL = os.environ.get("IMAGE_URL", "")
LAT = os.environ.get("LAT")
LON = os.environ.get("LON")
UNITS = os.environ.get("UNITS", "metric")

if not TELEGRAM_TOKEN or not OPENWEATHER_KEY:
    raise SystemExit("⚠️ لطفاً مقادیر TELEGRAM_TOKEN و OPENWEATHER_KEY را تنظیم کنید.")

# --- توابع دریافت داده‌ها (استفاده از APIهای پایدار 2.5) ---
def geocode_place(place_name):
    # API Geocoding
    url = f"http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": place_name, "limit": 1, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError("❌ مکان موردنظر پیدا نشد: " + place_name)
    return float(data[0]["lat"]), float(data[0]["lon"])

def fetch_current_weather(lat, lon):
    # Current Weather API (جایگزین OneCall برای اطلاعات فعلی)
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "units": UNITS, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_forecast(lat, lon):
    # 5-Day / 3-Hour Forecast API (برای پیش بینی ساعتی و min/max دما)
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"lat": lat, "lon": lon, "units": UNITS, "appid": OPENWEATHER_KEY, "cnt": 8} 
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_air_pollution(lat, lon):
    # Air Pollution API
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# --- قالب پیام نهایی ---
def format_message(region_name, current_json, forecast_json, air_json):
    # زمان فعلی به وقت ایران (UTC + 3.5 ساعت) + تبدیل به شمسی
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    date_fa = j_now.strftime("%Y/%m/%d")
    time_fa = j_now.strftime("%H:%M")

    # داده‌های آب و هوای فعلی
    current = current_json
    desc = current.get("weather", [{}])[0].get("description", "—")
    temp = round(current.get("main", {}).get("temp", 0), 1)
    humidity = current.get("main", {}).get("humidity", "—")

    # حداقل و حداکثر دما از پیش‌بینی 24 ساعت آینده
    temps = [i["main"]["temp"] for i in forecast_json.get("list", [])[:8] if "main" in i]
    temp_min = round(min(temps), 1) if temps else "—"
    temp_max = round(max(temps), 1) if temps else "—"

    # احتمال بارش
    pop = int(forecast_json.get("list", [{}])[0].get("pop", 0) * 100)

    # شاخص کیفیت هوا (AQI)
    aq = air_json.get("list", [{}])[0] if air_json else {}
    aqi = aq.get("main", {}).get("aqi", "—")
    aqi_map = {
        1: "🟢 خیلی تمیز — کیفیت عالی", 2: "🟢 خوب — هوا سالم است",
        3: "🟡 متوسط — کمی ناسالم برای افراد حساس", 4: "🟠 ناسالم — افراد حساس باید احتیاط کنند",
        5: "🔴 بسیار ناسالم — خطرناک برای عموم",
    }
    aqi_text = aqi_map.get(aqi, "⚪️ نامشخص")

    # پیش‌بینی ۱۲ ساعت آینده
    forecast_lines = []
    for h in forecast_json.get("list", [])[:4]:
        ts = datetime.datetime.utcfromtimestamp(h["dt"]) + datetime.timedelta(hours=3.5)
        j_ts = jdatetime.datetime.fromgregorian(datetime=ts)
        time_str = j_ts.strftime("%H:%M")
        w = h.get("weather", [{}])[0].get("description", "")
        t = round(h.get("main", {}).get("temp", 0), 1)
        p = int(h.get("pop", 0) * 100)
        forecast_lines.append(f"🕒 {time_str} | 🌤 {w} | 🌡 {t}° | ☔ {p}% احتمال بارش")

    forecast_text = "\n".join(forecast_lines)

    # پیام خروجی
    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n"
        f"📍 منطقه: {region_name}\n"
        f"📅 تاریخ: {date_fa}\n"
        f"⏰ ساعت: {time_fa}\n\n"
        f"وضعیت جوی: {desc}\n"
        f"دمای فعلی: {temp}°C\n"
        f"رطوبت: {humidity}%\n"
        f"احتمال بارش: {pop}%\n"
        f"حداقل دما: {temp_min}°C\n"
        f"حداکثر دما: {temp_max}°C\n"
        f"شاخص کیفیت هوا: {aqi_text}\n\n"
        f"<b>🔮 پیش‌بینی ۱۲ ساعت آینده:</b>\n{forecast_text}"
    )

    return msg

# --- توابع ارسال پیام ---
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
    air = fetch_air_pollution(latf, lonf)
    
    caption = format_message(REGION_NAME, current_weather, forecast, air)

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
