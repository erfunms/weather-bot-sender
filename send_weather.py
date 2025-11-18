#!/usr/bin/env python3
# send_weather.py (Ultimate Final Version: Stable AQI, Code Block for Guaranteed LTR)

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
WEATHER_TRANSLATIONS = {
    "clear-day": "آسمان صاف ☀️", "clear-night": "آسمان صاف ☀️", 
    "cloudy": "ابری ☁️", "partly-cloudy-day": "نیمه ابری 🌤️",
    "partly-cloudy-night": "نیمه ابری 🌤️", "rain": "باران 🌧️", 
    "snow": "برف ❄️", "wind": "بادی 🌬️", "fog": "مه 🌫️",
    "sleet": "باران و برف 🌨️", "hail": "تگرگ 🧊",
    "thunderstorm": "تندرباد/رعد و برق ⛈️", "default": "نامشخص ❓"
}

def get_aqi_status(aqi_value):
    if aqi_value is None or aqi_value == "—":
        return "⚪️ نامشخص"
    try:
        aqi = int(aqi_value)
    except ValueError:
        return "⚪️ نامشخص"
        
    if aqi <= 50: return "🟢 پاک — کیفیت هوا رضایت‌بخش است."
    elif aqi <= 100: return "🟡 قابل قبول — احتیاط برای افراد حساس."
    elif aqi <= 150: return "🟠 ناسالم برای گروه‌های حساس — فعالیت‌های طولانی‌مدت را محدود کنید."
    elif aqi <= 200: return "🔴 ناسالم — همه ممکن است اثرات بهداشتی را تجربه کنند."
    elif aqi <= 300: return "🟣 بسیار ناسالم — هشدار سلامت: خطرناک برای عموم."
    else: return "🟤 خطرناک — وضعیت اضطراری سلامت."

# --- توابع دریافت داده‌ها ---
def fetch_weather_data(lat, lon):
    """دریافت داده‌های آب و هوا (جاری و پیش‌بینی) از Visual Crossing"""
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
    """دریافت شاخص کیفیت هوا (AQI) از AQICN (بازگشت به جستجوی عمومی تهران)"""
    # ⬅️ بازگشت به جستجوی عمومی تهران برای جلوگیری از خطای "منحل شدن" ایستگاه خاص
    url = "https://api.waqi.info/feed/tehran/" 
    
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
    now_gregorian_iran = datetime.datetime.utcnow() + datetime.timedelta(hours=3.5)
    j_now = jdatetime.datetime.fromgregorian(datetime=now_gregorian_iran)
    date_fa = j_now.strftime("%Y/%m/%d")
    
    current = weather_json.get("currentConditions", {})
    desc = current.get("icon", "default")
    desc_fa = WEATHER_TRANSLATIONS.get(desc, WEATHER_TRANSLATIONS["default"]) 
    temp_current = round(current.get("temp", 0), 1) 
    humidity = current.get("humidity", "—")
    pop = int(current.get("precipprob", 0)) 
    
    
    # ----------------------------------------------------
    # منطق محاسبه حداقل و حداکثر دما برای ۲۴ ساعت آینده (پویا)
    # ----------------------------------------------------
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
        temp_min_24h = round(min(temps_in_24h), 1)
        temp_max_24h = round(max(temps_in_24h), 1)
    else:
        temp_min_24h = temp_max_24h = "—" 
    # ----------------------------------------------------
    
    aqi = str(aqi_value)
    aqi_text = get_aqi_status(aqi_value)

    # ⬅️ منطق پیش‌بینی ۱۲ ساعت در ۴ بازه
    forecast_lines = []
    start_index = 0
    
    for i, h in enumerate(hours_list):
        full_hour_utc = datetime.datetime.utcfromtimestamp(h.get('datetimeEpoch'))
        if start_time_utc < full_hour_utc:
             start_index = i
             break
        
    # ⚠️ استفاده از فضاهای ثابت برای تراز بندی در Code Block
    
    for i in range(4): # 4 نقطه زمانی
        index_to_check = start_index + (i * 3)
        
        if index_to_check >= len(hours_list):
             break 
            
        h = hours_list[index_to_check]
        
        full_hour_utc = datetime.datetime.utcfromtimestamp(h.get('datetimeEpoch'))
        ts_gregorian = full_hour_utc + datetime.timedelta(hours=3.5)
        j_ts = jdatetime.datetime.fromgregorian(datetime=ts_gregorian)
        time_str = j_ts.strftime("%H:%M") 

        w = h.get("icon", "default")
        w_fa = WEATHER_TRANSLATIONS.get(w, WEATHER_TRANSLATIONS["default"])
        t = round(h.get("temp", 0), 1)
        p = int(h.get("precipprob", 0))
        
        # ⬅️ قالب‌بندی نهایی: استفاده از فضای ثابت و | ساده (LTR تضمین شده توسط <pre>)
        
        # ساختار: 🕒 HH:MM | وضعیت جوی | 🌡 T°C | ☔ P% احتمال بارش 
        # استفاده از f-string و فاصله گذاری برای تراز (فقط در <pre> کار می کند)
        
        forecast_line = (
            f"🕒 {time_str:<5} | {w_fa:<10} | 🌡 {t}°C | ☔ {p}% احتمال بارش"
        )
        forecast_lines.append(forecast_line) 

    # ⬅️ محصور کردن پیش‌بینی در تگ <pre> برای اجبار به نمایش LTR و فونت Monospace
    forecast_text = "<pre>\n" + "\n".join(forecast_lines) + "\n</pre>" 

    # ⬅️ پیام خروجی نهایی
    msg = (
        f"🌦 <b>وضعیت آب‌وهوای امروز</b>\n" 
        f"📍 منطقه: {region_name}\n"
        f"📅 تاریخ: {date_fa}\n"
        f"وضعیت جوی: {desc_fa}\n"
        f"دمای فعلی: {temp_current}°C\n"
        f"رطوبت: {humidity}%\n"
        f"احتمال بارش: {pop}%\n"
        f"حداقل دما: {temp_min_24h}°C\n"
        f"حداکثر دما: {temp_max_24h}°C\n"
        f"شاخص کیفیت هوا ({aqi}): {aqi_text}\n\n"
        f"<b>پیش‌بینی ۱۲ ساعت آینده:</b>\n"
        f"{forecast_text}" 
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
    latf = float(LAT)
    lonf = float(LON)
    
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
