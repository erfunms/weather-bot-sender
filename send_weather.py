#!/usr/bin/env python3
# send_weather.py (Final Strategy: Vertical Layout & Official AQI Mirror)

import os
import requests
import datetime
import time
import jdatetime

# --- تنظیمات اصلی ---
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
    raise SystemExit("⚠️ لطفاً تمام مقادیر لازم را تنظیم کنید.")


# --- دیکشنری‌های ترجمه ---
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
    elif aqi <= 150: return "🟠 ناسالم (گروه‌های حساس)"
    elif aqi <= 200: return "🔴 ناسالم (همه)"
    elif aqi <= 300: return "🟣 بسیار ناسالم"
    else: return "🟤 خطرناک"

# --- توابع دریافت داده‌ها ---
def fetch_weather_data(lat, lon):
    """دریافت داده‌های آب و هوا از Visual Crossing"""
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

def fetch_air_pollution(lat, lon):
    """دریافت AQI از AQICN (میانگین کل تهران)"""
    # استفاده از feed/tehran/ که معمولاً با سایت کنترل کیفیت هماهنگ است
    url = "https://api.waqi.info/feed/tehran/" 
    params = {"token": AQICN_TOKEN}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "ok" and data.get("data"):
            return data["data"].get("aqi", "—")
    except:
        pass
    return "—" 


# --- قالب پیام نهایی ---
def format_message(region_name, weather_json, aqi_value):
    # زمان فعلی به وقت ایران
    now_gregorian_iran = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    j_now = jdatetime.datetime.fromgregorian(datetime=now_gregorian_iran)
    date_fa = j_now.strftime("%Y/%m/%d")
    
    current = weather_json.get("currentConditions", {})
    desc = current.get("icon", "default")
    desc_fa = WEATHER_TRANSLATIONS.get(desc, WEATHER_TRANSLATIONS["default"]) 
    temp_current = round(current.get("temp", 0), 1) 
    humidity = current.get("humidity", "—")
    pop = int(current.get("precipprob", 0)) 
    
    # --- محاسبه حداقل/حداکثر دما (۲۴ ساعت آینده) ---
    hours_list = []
    for day in weather_json.get("days", []):
        hours_list.extend(day.get("hours", []))

    start_time_utc = datetime.datetime.utcnow()
    end_time_utc = start_time_utc + datetime.timedelta(hours=24)
    temps_in_24h = []
    
    for h in hours_list:
        full_hour_utc = datetime.datetime.utcfromtimestamp(h.get('datetimeEpoch'))
        if start_time_utc <= full_hour_utc <= end_time_utc:
            temps_in_24h.append(h.get("temp"))

    if temps_in_24h:
        temp_min = round(min(temps_in_24h), 1)
        temp_max = round(max(temps_in_24h), 1)
    else:
        temp_min = temp_max = "—" 
    
    aqi = str(aqi_value)
    aqi_text = get_aqi_status(aqi_value)

    # --- ساخت بخش پیش‌بینی (طراحی دو خطی برای رفع مشکل نگارشی) ---
    forecast_lines = []
    start_index = 0
    
    for i, h in enumerate(hours_list):
        full_hour_utc = datetime.datetime.utcfromtimestamp(h.get('datetimeEpoch'))
        if start_time_utc < full_hour_utc:
             start_index = i
             break
        
    for i in range(4): 
        index_to_check = start_index + (i * 3)
        if index_to_check >= len(hours_list): break 
            
        h = hours_list[index_to_check]
        full_hour_utc = datetime.datetime.utcfromtimestamp(h.get('datetimeEpoch'))
        ts_gregorian = full_hour_utc + datetime.timedelta(hours=3.5)
        time_str = jdatetime.datetime.fromgregorian(datetime=ts_gregorian).strftime("%H:%M")

        w = h.get("icon", "default")
        w_fa = WEATHER_TRANSLATIONS.get(w, WEATHER_TRANSLATIONS["default"])
        t = round(h.get("temp", 0), 1)
        p = int(h.get("precipprob", 0))
        
        # ✅ تغییر استراتژی: نمایش در دو خط برای جلوگیری از تداخل فارسی/انگلیسی
        # خط اول: ساعت و وضعیت جوی
        # خط دوم: دما و بارش (کاملاً جدا از متن فارسی)
        line = (
            f"🕒 <b>{time_str}</b>  {w_fa}\n"
            f"   🌡 {t}°C    ☔ {p}% بارش\n"
        )
        forecast_lines.append(line)

    forecast_text = "".join(forecast_lines) 

    # پیام خروجی
    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n" 
        f"📍 {region_name} | 📅 {date_fa}\n\n"
        f"وضعیت: {desc_fa}\n"
        f"دما: {temp_current}°C  (🔽{temp_min} 🔼{temp_max})\n"
        f"رطوبت: {humidity}% | بارش: {pop}%\n"
        f"کیفیت هوا: {aqi} ({aqi_text})\n\n"
        f"<b>🔮 پیش‌بینی ۱۲ ساعت آینده:</b>\n\n"
        f"{forecast_text}" 
    )

    return msg

# --- توابع ارسال پیام ---
def send_photo(chat_id, photo_url, caption_html):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": chat_id, "caption": caption_html, "parse_mode": "HTML", "photo": photo_url}
    requests.post(url, data=data, timeout=20)

def send_message(chat_id, text_html):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text_html, "parse_mode": "HTML"}
    requests.post(url, data=data, timeout=20)

# --- اجرای اصلی ---
def main():
    latf = float(LAT)
    lonf = float(LON)
    
    weather_data = fetch_weather_data(latf, lonf)
    aqi_value = fetch_air_pollution(latf, lonf) 
    caption = format_message(REGION_NAME, weather_data, aqi_value)

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    for cid in chat_ids:
        try:
            if IMAGE_URL: send_photo(cid, IMAGE_URL, caption)
            else: send_message(cid, caption)
            time.sleep(1)
        except Exception as e:
            print(f"Error sending to {cid}: {e}") 

if __name__ == "__main__":
    main()
