#!/usr/bin/env python3
# send_weather.py
import os
import requests
import datetime
import time

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")         # Example: "780130... (don't hardcode)"
OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY")       # Example: "d2b7d8..."
CHAT_IDS = os.environ.get("CHAT_IDS", "")                 # comma-separated chat ids, e.g. "12345,-98765"
REGION_NAME = os.environ.get("REGION_NAME", "ئانزده خرداد")
IMAGE_URL = os.environ.get("IMAGE_URL", "")               # public URL to your static image (or empty)
LAT = os.environ.get("LAT")                               # optional: latitude
LON = os.environ.get("LON")                               # optional: longitude
UNITS = os.environ.get("UNITS", "metric")                 # metric (C) or imperial

if not TELEGRAM_TOKEN or not OPENWEATHER_KEY:
    raise SystemExit("Please set TELEGRAM_TOKEN and OPENWEATHER_KEY as environment variables.")

# --- توابع دریافت اطلاعات ---

def geocode_place(place_name):
    # Geocoding API (دست نخورده)
    url = f"http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": place_name, "limit": 1, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError("Geocoding failed, no results for place: " + place_name)
    return float(data[0]["lat"]), float(data[0]["lon"])

def fetch_current_weather(lat, lon):
    # Current Weather API (جایگزین One Call برای اطلاعات فعلی)
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat, "lon": lon,
        "units": UNITS,
        "appid": OPENWEATHER_KEY
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_forecast(lat, lon):
    # 5-Day / 3-Hour Forecast API (جایگزین One Call برای پیش‌بینی ساعتی/روزانه)
    url = "https://api.openweathermap.org/data/2.5/forecast"
    # cnt=8 به معنی 8 پیش بینی (8 * 3 ساعت = 24 ساعت پیش بینی)
    params = {
        "lat": lat, "lon": lon,
        "units": UNITS,
        "appid": OPENWEATHER_KEY,
        "cnt": 8 
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_air_pollution(lat, lon):
    # Air Pollution API (دست نخورده)
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

# --- تابع قالب بندی پیام (اصلاح شده) ---

def format_message(region_name, current_json, forecast_json, air_json):
    now = datetime.datetime.utcnow() + datetime.timedelta() 
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")
    
    # استخراج داده‌های فعلی از Current Weather API
    current = current_json
    desc = current.get("weather", [{}])[0].get("description", "—").capitalize()
    temp = current.get("main", {}).get("temp", "—")
    humidity = current.get("main", {}).get("humidity", "—")
    
    # از داده‌های Current Weather برای حداقل/حداکثر امروز استفاده می‌شود 
    # (API 5-Day/3-Hour Forecast min/max دمای روز را مستقیماً نمی‌دهد)
    temp_min = current.get("main", {}).get("temp_min", "—")
    temp_max = current.get("main", {}).get("temp_max", "—")

    # احتمال بارش (POP) از اولین پیش بینی ساعتی (3 ساعت آینده)
    pop = forecast_json.get("list", [{}])[0].get("pop", 0) * 100 if forecast_json.get("list") else 0

    # Air quality (دست نخورده)
    aq = air_json.get("list", [{}])[0] if air_json else {}
    aqi = aq.get("main", {}).get("aqi", "—")  # 1..5 scale for OpenWeather
    components = aq.get("components", {})

    # 12-hour forecast summary
    # 4 آیتم اول از لیست پیش بینی (4 * 3 ساعت = 12 ساعت)
    hourly = forecast_json.get("list", [])[:4] 
    forecast_lines = []
    for h in hourly:
        ts = datetime.datetime.utcfromtimestamp(h["dt"])
        time_str = ts.strftime("%H:%M")
        w = h.get("weather", [{}])[0].get("description", "")
        t = h.get("main", {}).get("temp", "—")
        p = int(h.get("pop", 0) * 100)
        forecast_lines.append(f"{time_str}: {w}, {t}° — {p}% بارش")

    forecast_text = "\n".join(forecast_lines)

    msg = f"<b>{region_name}</b>\n{now_str}\n\n" \
          f"وضعیت: {desc}\n" \
          f"دمای فعلی: {temp}°\n" \
          f"رطوبت: {humidity}%\n" \
          f"احتمال بارش (ساعت آینده): {int(pop)}%\n" \
          f"حداقل/حداکثر روز: {temp_min}° / {temp_max}°\n" \
          f"آلودگی هوا (AQI): {aqi}\n"

    # Optionally append major pollutant values
    if components:
        comp_summary = ", ".join([f"{k}:{int(v)}" for k, v in components.items() if v is not None][:5])
        msg += f"اجزای آلودگی: {comp_summary}\n"

    msg += "\n<b>پیش‌بینی ۱۲ ساعت آینده</b>:\n" + forecast_text
    return msg

# --- توابع ارسال پیام (دست نخورده) ---

def send_photo(chat_id, photo_url, caption_html):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {"chat_id": chat_id, "caption": caption_html, "parse_mode": "HTML"}
    files = {"photo": requests.get(photo_url, stream=True).raw} if photo_url else None
    
    if photo_url:
        data["photo"] = photo_url
        r = requests.post(send_url, data=data, timeout=20)
    else:
        # If no image, fallback to sendMessage
        send_message(chat_id, caption_html)
        return
    r.raise_for_status()
    return r.json()

def send_message(chat_id, text_html):
    send_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text_html, "parse_mode": "HTML"}
    r = requests.post(send_url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()

# --- تابع main (اصلاح شده) ---

def main():
    global LAT, LON
    if not LAT or not LON:
        try:
            lat, lon = geocode_place(REGION_NAME)
            LAT, LON = str(lat), str(lon)
        except Exception as e:
            raise SystemExit(f"Geocoding failed: {e}")
            
    latf, lonf = float(LAT), float(LON)

    # فراخوانی توابع جدید
    current_weather = fetch_current_weather(latf, lonf)
    forecast = fetch_forecast(latf, lonf)
    air = fetch_air_pollution(latf, lonf)
    
    # فراخوانی format_message با ورودی‌های جدید
    caption = format_message(REGION_NAME, current_weather, forecast, air)

    chat_ids = [c.strip() for c in CHAT_IDS.split(",") if c.strip()]
    if not chat_ids:
        raise SystemExit("No CHAT_IDS set. Set CHAT_IDS env var (comma separated).")

    for cid in chat_ids:
        try:
            if IMAGE_URL:
                send_photo(cid, IMAGE_URL, caption)
            else:
                send_message(cid, caption)
            time.sleep(1)  # small pause to avoid rate limits
        except Exception as e:
            print(f"Failed to send to {cid}: {e}")

if __name__ == "__main__":
    main()
