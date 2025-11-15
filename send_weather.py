#!/usr/bin/env python3
# send_weather.py (Final Version: Visual Crossing, 12-Hour Forecast in 4 Intervals, SyntaxError Fix)

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
    raise SystemExit("⚠️ لطفاً تمام مقادیر لازم (TELEGRAM_TOKEN, VISUALCROSSING_KEY, AQICN_TOKEN) را تنظیم کنید.")


# --- دیکشنری‌های ترجمه ---
# ⬅️ حذف شب/روز از توضیحات وضعیت جوی
WEATHER_TRANSLATIONS = {
    "clear-day": "آسمان صاف ☀️", 
    "clear-night": "آسمان صاف ☀️", 
    "cloudy": "ابری ☁️", 
    "partly-cloudy-day": "نیمه ابری 🌤️",
    "partly-cloudy-night": "نیمه ابری 🌤️", 
    "rain": "باران 🌧️", "snow": "برف ❄️",
    "wind": "بادی 🌬️", "fog": "مه 🌫️",
    "sleet": "باران و برف 🌨️", "hail": "تگرگ 🧊",
    "thunderstorm": "تندرباد/رعد و برق ⛈️",
    "default": "نامشخص ❓"
}

# ⬅️ مقیاس‌های دقیق AQI بر اساس استاندارد EPA
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

# --- توابع دریافت داده‌ها ---
def fetch_weather_data(lat, lon):
    """دریافت داده‌های آب و هوا (جاری و پیش‌بینی) از Visual Crossing"""
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}/today"
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
    """دریافت شاخص کیفیت هوا (AQI) از AQICN"""
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
    params = {"token": AQICN_TOKEN}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    
    if data.get("status") == "ok" and data.get("data") and data["data"].get("aqi"):
        return data["data"]["aqi"]
    return "—" 


# --- قالب پیام نهایی ---
def format_message(region_name, weather_json, aqi_value):
    # زمان فعلی به وقت ایران (UTC + 3.5 ساعت) + تبدیل به شمسی
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    j_now = jdatetime.datetime.fromgregorian(datetime=now)
    date_fa = j_now.strftime("%Y/%m/%d")
    
    # ⬅️ استخراج داده‌های فعلی
    current = weather_json.get("currentConditions", {})
    
    desc = current.get("icon", "default")
    desc_fa = WEATHER_TRANSLATIONS.get(desc, WEATHER_TRANSLATIONS["default"]) 
    temp = round(current.get("temp", 0), 1)
    humidity = current.get("humidity", "—")
    pop = int(current.get("precipprob", 0)) 
    
    # ⬅️ استخراج داده‌های روزانه برای حداقل و حداکثر دما
    daily_data = weather_json.get("days", [{}])[0]
    temp_min = round(daily_data.get("tempmin", 0), 1)
    temp_max = round(daily_data.get("tempmax", 0), 1)

    # شاخص کیفیت هوا (AQI)
    aqi = str(aqi_value)
    aqi_text = get_aqi_status(aqi_value)

    # ⬅️ منطق پیش‌بینی ۱۲ ساعت در ۴ بازه
    forecast_lines = []
    hours_list = weather_json.get("days", [{}])[0].get("hours", [])
    
    # ساعت فعلی UTC 
    now_utc = datetime.datetime.utcnow() 
    current_hour_utc = now_utc.hour 
    current_minute_utc = now_utc.minute

    # پیدا کردن شاخص شروع: اولین ساعت کامل آینده
    start_index = 0
    
    # اگر دقیقه فعلی بعد از 30 باشد، اولین نقطه پیش‌بینی باید ساعت بعدی باشد.
    if current_minute_utc >= 30: 
        target_hour_utc = (current_hour_utc + 1) % 24 
    else:
        # اگر دقیقه کمتر از 30 است، از ساعت فعلی شروع می‌کنیم
        target_hour_utc = current_hour_utc

    # جستجوی شاخص مربوط به ساعت هدف
    for i, h in enumerate(hours_list):
        hour_api_utc = int(h['datetime'].split(':')[0])
        minute_api = int(h['datetime'].split(':')[1])
        
        if hour_api_utc == target_hour_utc and minute_api == 0:
             start_index = i
             break
        
        if hour_api_utc > target_hour_utc:
             start_index = i
             break


    # پیش‌بینی ۱۲ ساعت آینده در ۴ بازه (هر ۳ ساعت یکبار)
    for i in range(4): # 4 نقطه زمانی
        index_to_check = start_index + (i * 3) # پرش‌های 3 ساعته: 0, 3, 6, 9
        
        # اگر شاخص از محدوده لیست امروز خارج شد
        if index_to_check >= len(hours_list):
             break 
            
        h = hours_list[index_to_check]
        
        # تبدیل زمان API (که UTC است) به زمان ایران (+ 3.5 ساعت) و شمسی
        time_api_str = h['datetime']
        hour_api_utc = int(time_api_str.split(':')[0])
        minute_api = int(time_api_str.split(':')[1])
        
        ts_gregorian = datetime.datetime(j_now.year, j_now.month, j_now.day, hour_api_utc, minute_api) + datetime.timedelta(hours=3.5)
        j_ts = jdatetime.datetime.fromgregorian(datetime=ts_gregorian)
        time_str = j_ts.strftime("%H:%M") # زمان به وقت ایران

        w = h.get("icon", "default")
        w_fa = WEATHER_TRANSLATIONS.get(w, WEATHER_TRANSLATIONS["default"])
        t = round(h.get("temp", 0), 1)
        p = int(h.get("precipprob", 0))
        
        # ⬅️ رفع خطای SyntaxError در این خط
        forecast_lines.append(f"🕒 {time_str} | {w_fa} | 🌡 {t}°C | ☔ {p}% احتمال بارش") 

    forecast_text = "\n".join(forecast_lines) 

    # ⬅️ پیام خروجی (با حذف اعلام ساعت، منبع و ایموجی گوی)
    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n" 
        f"📍 منطقه: {region_name}\n"
        f"📅 تاریخ: {date_fa}\n"
        f"وضعیت جوی: {desc_fa}\n"
        f"دمای فعلی: {temp}°C\n"
        f"رطوبت: {humidity}%\n"
        f"احتمال بارش: {pop}%\n"
        f"حداقل دما: {temp_min}°C\n"
        f"حداکثر دما: {temp_max}°C\n"
        f"شاخص کیفیت هوا ({aqi}): {aqi_text}\n\n"
        f"<b>پیش‌بینی ۱۲ ساعت آینده:</b>\n{forecast_text}" 
    )

    return msg

# --- توابع ارسال پیام (بدون تغییر) ---
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

# --- اجرای اصلی (بدون تغییر) ---
def main():
    latf, lonf = float(LAT), float(LON)
    
    weather_data = fetch_weather_data(latf, lonf)
    aqi_value = fetch_air_pollution(latf, lonf) 
    
    caption = format_message(REGION_NAME, weather_data, aqi_value)

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
