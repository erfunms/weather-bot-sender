import os, requests, datetime

# اطلاعات مورد نیاز از تنظیمات GitHub به‌صورت خودکار گرفته می‌شود
TOKEN = os.environ.get("TELEGRAM_TOKEN")
OW_KEY = os.environ.get("OPENWEATHER_KEY")
CHAT_IDS = os.environ.get("CHAT_IDS")
REGION = os.environ.get("REGION_NAME", "ئانزده خرداد")
IMAGE = os.environ.get("IMAGE_URL", "")

def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OW_KEY}&units=metric&lang=fa"
    r = requests.get(url)
    return r.json()

def get_forecast(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OW_KEY}&units=metric&lang=fa"
    r = requests.get(url)
    return r.json()

def get_air(city):
    geo = requests.get(f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OW_KEY}").json()
    lat, lon = geo[0]["lat"], geo[0]["lon"]
    air = requests.get(f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OW_KEY}").json()
    return air

def send_message(chat_id, text, photo=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto" if photo else f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "parse_mode": "HTML"}
    if photo:
        data["photo"] = photo
        data["caption"] = text
    else:
        data["text"] = text
    requests.post(url, data=data)

def main():
    w = get_weather(REGION)
    f = get_forecast(REGION)
    a = get_air(REGION)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    desc = w["weather"][0]["description"]
    temp = w["main"]["temp"]
    hum = w["main"]["humidity"]
    tmin, tmax = w["main"]["temp_min"], w["main"]["temp_max"]
    pop = f["list"][0]["pop"] * 100 if "pop" in f["list"][0] else 0
    aqi = a["list"][0]["main"]["aqi"]

    msg = f"<b>{REGION}</b>\n{now}\n\nوضعیت: {desc}\nدمای فعلی: {temp}°C\nرطوبت: {hum}%\nاحتمال بارش: {int(pop)}%\nحداقل: {tmin}° / حداکثر: {tmax}°\nآلودگی هوا (AQI): {aqi}\n\nپیش‌بینی ۱۲ ساعت آینده در حال آماده‌سازی است..."

    for cid in CHAT_IDS.split(","):
        send_message(cid.strip(), msg, IMAGE if IMAGE else None)

if __name__ == "__main__":
    main()
