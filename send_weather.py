#!/usr/bin/env python3
# send_weather.py (Updated for Visual Crossing API)

import os
import requests
import datetime
import time
import jdatetime

# --- تنظیمات اصلی ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
VISUALCROSSING_KEY = os.environ.get("VISUALCROSSING_KEY") # ⬅️ کلید جدید
AQICN_TOKEN = os.environ.get("AQICN_TOKEN") 
CHAT_IDS = os.environ.get("CHAT_IDS", "")
REGION_NAME = os.environ.get("REGION_NAME", "پانزده خرداد")
IMAGE_URL = os.environ.get("IMAGE_URL", "")
# مختصات جغرافیایی شما (تهران، پانزده خرداد)
LAT = os.environ.get("LAT", "35.6764")
LON = os.environ.get("LON", "51.4181")
UNITS = os.environ.get("UNITS", "metric") # متریک برای سلسیوس

if not TELEGRAM_TOKEN or not VISUALCROSSING_KEY or not AQICN_TOKEN:
    raise SystemExit("⚠️ لطفاً تمام مقادیر لازم (TELEGRAM_TOKEN, VISUALCROSSING_KEY, AQICN_TOKEN) را تنظیم کنید.")


# --- دیکشنری‌های ترجمه ---
# کدهای وضعیت جوی Visual Crossing و ترجمه آن‌ها
WEATHER_TRANSLATIONS = {
    "clear-day": "آسمان صاف ☀️", "clear-night": "آسمان صاف (شب) 🌙",
    "cloudy": "ابری ☁️", "partly-cloudy-day": "نیمه ابری 🌤️",
    "partly-cloudy-night": "نیمه ابری (شب) 🌥️", 
    "rain": "باران 🌧️", "snow": "برف ❄️",
    "wind": "بادی 🌬️", "fog": "مه 🌫️",
    "sleet": "باران و برف 🌨️", "hail": "تگرگ 🧊",
    "thunderstorm": "تندرباد/رعد و برق ⛈️",
    "default": "نامشخص ❓"
}

# ⬅️ مقیاس‌های دقیق AQI بر اساس استاندارد EPA (بدون تغییر)
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
    # ⬅️ استفاده از مختصات و متغیر جدید
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
    """دریافت شاخص کیفیت هوا (AQI) از AQICN (بدون تغییر)"""
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
    time_fa = j_now.strftime("%H:%M")

    # ⬅️ استخراج داده‌های فعلی
    current = weather_json.get("currentConditions", {})
    
    desc = current.get("icon", "default")
    desc_fa = WEATHER_TRANSLATIONS.get(desc, WEATHER_TRANSLATIONS["default"]) 
    temp = round(current.get("temp", 0), 1)
    humidity = current.get("humidity", "—")
    pop = int(current.get("precipprob", 0)) # احتمال بارش فعلی
    
    # ⬅️ استخراج داده‌های روزانه برای حداقل و حداکثر دما
    daily_data = weather_json.get("days", [{}])[0]
    temp_min = round(daily_data.get("tempmin", 0), 1)
    temp_max = round(daily_data.get("tempmax", 0), 1)

    # شاخص کیفیت هوا (AQI)
    aqi = str(aqi_value)
    aqi_text = get_aqi_status(aqi_value)

    # ⬅️ پیش‌بینی ۱۲ ساعت آینده (۴ ساعت بعدی)
    forecast_lines = []
    # ما به دنبال ۴ ساعت آینده (از ساعت فعلی) هستیم. 
    # V.C تمام ۲۴ ساعت را برمی‌گرداند، پس باید ساعت فعلی را پیدا کنیم.
    
    hours_list = weather_json.get("days", [{}])[0].get("hours", [])
    
    # یافتن ساعت فعلی (با توجه به زمان ایران)
    current_hour = now.hour
    
    # پیدا کردن شاخص شروع (نزدیک‌ترین ساعت به ساعت فعلی)
    start_index = 0
    for i, h in enumerate(hours_list):
        # زمان در API به صورت UTC است، پس باید آن را با زمان ایران مقایسه کنیم
        hour_utc = int(h['datetime'].split(':')[0])
        if hour_utc >= now.hour:
             start_index = i
             break

    # پیش‌بینی ۴ ساعت آینده از ساعت فعلی
    for h in hours_list[start_index:start_index + 4]:
        
        # زمان در API به صورت HH:MM:SS است
        time_str_api = h['datetime']
        
        # تبدیل زمان API (که UTC است) به زمان ایران (+ 3.5 ساعت) و شمسی
        # چون Visual Crossing زمان‌ها را به صورت HH:MM:SS برمی‌گرداند، فقط باید ساعت را جلو ببریم
        hour_utc = int(time_str_api.split(':')[0])
        # ما فقط نیاز به ساعت داریم، چون UTC است، باید 3.5 ساعت اضافه کنیم
        # این یک تقریب برای ایران است
        ts = datetime.datetime.strptime(time_str_api.split(':')[0], "%H")
        
        # تبدیل به زمان ایران و شمسی
        # چون Visual Crossing فقط ساعت را می‌دهد و ما تاریخ را نمی‌دانیم، از تاریخ امروز استفاده می‌کنیم
        ts_gregorian = datetime.datetime(j_now.year, j_now.month, j_now.day, hour_utc) + datetime.timedelta(hours=3.5)
        j_ts = jdatetime.datetime.fromgregorian(datetime=ts_gregorian)
        time_str = j_ts.strftime("%H:%M")
        
        w = h.get("icon", "default")
        w_fa = WEATHER_TRANSLATIONS.get(w, WEATHER_TRANSLATIONS["default"])
        t = round(h.get("temp", 0), 1)
        p = int(h.get("precipprob", 0))
        
        forecast_lines.append(f"🕒 {time_str} | {w_fa} | 🌡 {t}° | ☔ {p}% احتمال بارش") 

    forecast_text = "\n".join(forecast_lines) 

    # پیام خروجی
    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b> (منبع: Visual Crossing)\n"
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
        f"<b>🔮 پیش‌بینی ۴ ساعت آینده:</b>\n{forecast_text}"
    )

    return msg

# --- توابع ارسال پیام (بدون تغییر) ---
def send_photo(chat_id, photo_url, caption_html):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    data = {
        "chat_id": chat_id, 
        "caption": caption_html, 
        "parse_mode": "HTML", 
        "photo": photo_url,
    }
    r = requests.post(url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()

def send_message(chat_id, text_html):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    data = {
        "chat_id": chat_id, 
        "text": text_html, 
        "parse_mode": "HTML",
    }
    r = requests.post(url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()

# --- اجرای اصلی ---
def main():
    latf, lonf = float(LAT), float(LON)
    
    # ⬅️ فراخوانی تابع جدید
    weather_data = fetch_weather_data(latf, lonf)
    aqi_value = fetch_air_pollution(latf, lonf) 
    
    # ⬅️ فراخوانی تابع قالب‌بندی جدید
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
