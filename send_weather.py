#!/usr/bin/env python3
# send_weather.py (Final Fix: Applying LRM to Header and Footer)

import os
import requests
import datetime
import time
import jdatetime

# --- تنظیمات ---
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

# --- دیکشنری ---
WEATHER_TRANSLATIONS = {
    "clear-day": "آسمان صاف ☀️", "clear-night": "آسمان صاف 🌙", 
    "cloudy": "ابری ☁️", "partly-cloudy-day": "نیمه ابری 🌤️",
    "partly-cloudy-night": "نیمه ابری ☁️", "rain": "باران 🌧️", 
    "snow": "برف ❄️", "wind": "بادی 🌬️", "fog": "مه 🌫️",
    "sleet": "باران و برف 🌨️", "hail": "تگرگ 🧊",
    "thunderstorm": "تندرباد/رعد و برق ⛈️", "default": "نامشخص ❓"
}

def get_aqi_status(aqi_value):
    if aqi_value is None or aqi_value == "—": return "⚪️ نامشخص"
    try:
        aqi = int(aqi_value)
    except ValueError: return "⚪️ نامشخص"
    if aqi <= 50: return "🟢 پاک"
    elif aqi <= 100: return "🟡 قابل قبول"
    elif aqi <= 150: return "🟠 ناسالم (حساس)"
    elif aqi <= 200: return "🔴 ناسالم (همه)"
    elif aqi <= 300: return "🟣 بسیار ناسالم"
    else: return "🟤 خطرناک"

# --- تابع کمکی برای اصلاح جهت متن (LRM) ---
def fix_text(text):
    """این تابع متن را بین دو کاراکتر نامرئی چپ-به-راست قرار می‌دهد تا جابجا نشود"""
    LRM = "\u200E"
    return f"{LRM}{text}{LRM}"

# --- دریافت داده ---
def fetch_weather_data(lat, lon):
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}"
    params = {"unitGroup": UNITS, "key": VISUALCROSSING_KEY, "contentType": "json", "include": "current,hours,days"}
    r = requests.get(url, params=params, timeout=15); r.raise_for_status()
    return r.json()

def fetch_air_pollution(lat, lon):
    url = "https://api.waqi.info/feed/tehran/" 
    params = {"token": AQICN_TOKEN}
    try:
        r = requests.get(url, params=params, timeout=15); r.raise_for_status(); data = r.json()
        if data.get("status") == "ok" and data.get("data"): return data["data"].get("aqi", "—")
    except: pass
    return "—" 

# --- فرمت پیام ---
def format_message(region_name, weather_json, aqi_value):
    # زمان
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    date_fa = j_now.strftime("%Y/%m/%d")
    
    # داده‌های فعلی
    current = weather_json.get("currentConditions", {})
    desc = WEATHER_TRANSLATIONS.get(current.get("icon", "default"), "نامشخص")
    temp_val = round(current.get("temp", 0), 1)
    
    # اصلاح نگارشی دمای فعلی (اضافه کردن LRM)
    temp_str = fix_text(f"{temp_val}°C")
    
    # محاسبه مینیمم/ماکزیمم
    hours = []
    for d in weather_json.get("days", []): hours.extend(d.get("hours", []))
    start = datetime.datetime.utcnow(); end = start + datetime.timedelta(hours=24)
    temps_24h = [h.get("temp") for h in hours if start <= datetime.datetime.utcfromtimestamp(h.get('datetimeEpoch')) <= end]
    
    # اصلاح نگارشی مینیمم/ماکزیمم
    t_min = fix_text(f"{round(min(temps_24h), 1)}°C") if temps_24h else "—"
    t_max = fix_text(f"{round(max(temps_24h), 1)}°C") if temps_24h else "—"
    
    # --- بخش پیش‌بینی ---
    forecast_lines = []
    start_idx = next((i for i, h in enumerate(hours) if datetime.datetime.utcfromtimestamp(h.get('datetimeEpoch')) > start), 0)
    
    for i in range(4):
        idx = start_idx + (i * 3)
        if idx >= len(hours): break
        h = hours[idx]
        
        ts = datetime.datetime.utcfromtimestamp(h.get('datetimeEpoch')) + datetime.timedelta(hours=3.5)
        time_str = jdatetime.datetime.fromgregorian(datetime=ts).strftime("%H:%M")
        w_fa = WEATHER_TRANSLATIONS.get(h.get("icon", "default"), "؟")
        
        t_forecast = round(h.get("temp", 0), 1)
        p_forecast = int(h.get("precipprob", 0))
        
        # اصلاح نگارشی مقادیر پیش‌بینی
        f_temp = fix_text(f"{t_forecast}°C")
        f_rain = fix_text(f"{p_forecast}%")
        
        line = f"🕒 {time_str} | {w_fa} | 🌡 {f_temp} | ☔ {f_rain} بارش"
        forecast_lines.append(line)

    # پیام نهایی
    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n"
        f"📍 منطقه: {region_name}\n"
        f"📅 تاریخ: {date_fa}\n"
        f"وضعیت: {desc}\n"
        f"دمای فعلی: {temp_str}\n" # حالا این درست نمایش داده می‌شود
        f"حداقل: {t_min} | حداکثر: {t_max}\n" # این‌ها هم درست می‌شوند
        f"کیفیت هوا: {aqi_value} ({get_aqi_status(aqi_value)})\n\n"
        f"<b>پیش‌بینی ۱۲ ساعت آینده:</b>\n" + "\n".join(forecast_lines)
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
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto" if IMAGE_URL else f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": cid, "caption" if IMAGE_URL else "text": msg, "parse_mode": "HTML"}
            if IMAGE_URL: data["photo"] = IMAGE_URL
            requests.post(url, data=data, timeout=20)
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__": main()
