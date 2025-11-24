import os
import requests
import datetime
from datetime import timezone, timedelta

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
VISUAL_API_KEY = os.getenv("VISUAL_API_KEY")

REGION_NAME = "پارک شهر (تهران)"

# ایستگاه پارک‌شهر
AQI_STATION_URL = "https://air.tehran.ir/api/onlineaqi/GetAllOnlineAQIDetails"

# Tehran coordinates
LAT = 35.6892
LON = 51.3890
# -----------------------------------------


# ===== TIME HELPERS =====
def now_tehran():
    return datetime.datetime.now(timezone.utc) + timedelta(hours=3.5)


def epoch_to_tehran(ts: int):
    return datetime.datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=3.5)


# ===== AQI PROCESSING =====
def get_aqi_status(aqi: int):
    if aqi <= 50:
        return "🔵 خوب"
    elif aqi <= 100:
        return "🟢 قابل قبول"
    elif aqi <= 150:
        return "🟡 ناسالم برای گروه‌های حساس"
    elif aqi <= 200:
        return "🟠 ناسالم"
    elif aqi <= 300:
        return "🔴 بسیار ناسالم"
    else:
        return "🟣 خطرناک"


def get_tehran_aqi():
    try:
        r = requests.get(AQI_STATION_URL, timeout=10)
        r.raise_for_status()
        data = r.json()

        for st in data:
            name = st.get("StationName", "")
            if "پارک شهر" in name:
                return int(st.get("AQI", 0))

        return None

    except Exception as e:
        print("AQI Error:", e)
        return None


# ===== WEATHER API =====
def get_weather():
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{LAT},{LON}?unitGroup=metric&include=hours&key={VISUAL_API_KEY}"

    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


# ===== MESSAGE FORMATTER =====
def format_message(region, weather, aqi_value):

    now = now_tehran().strftime("%H:%M")

    today = weather["days"][0]
    tomorrow = weather["days"][1]

    # next 12 hours
    current_time = datetime.datetime.now(timezone.utc)
    end_time = current_time + timedelta(hours=12)

    next_hours = [
        h for h in today["hours"]
        if current_time <= datetime.datetime.fromtimestamp(h["datetimeEpoch"], timezone.utc) <= end_time
    ]

    # Find next weather event
    next_event = None
    for h in today["hours"]:
        if datetime.datetime.fromtimestamp(h["datetimeEpoch"], timezone.utc) > current_time:
            if h.get("precip", 0) > 0:
                next_event = (h["conditions"], epoch_to_tehran(h["datetimeEpoch"]).strftime("%H:%M"))
                break

    # Build message
    msg = (
        f"🌤️ گزارش آب‌وهوا - {region}\n"
        f"⏰ ساعت: {now}\n\n"

        f"📌 وضعیت فعلی:\n"
        f"دمـا: {today['temp']}°C\n"
        f"رطـوبت: {today['humidity']}٪\n"
        f"احساس واقعی: {today['feelslike']}°C\n\n"

        f"🌫️ کیفیت هوا:\n"
        f"{aqi_value} - {get_aqi_status(aqi_value)}\n\n"

        f"☀️ پیش‌بینی امروز:\n"
        f"حداقل: {today['tempmin']}°C\n"
        f"حداکثر: {today['tempmax']}°C\n"
        f"خلاصه: {today['conditions']}\n\n"

        f"📅 فردا:\n"
        f"حداقل: {tomorrow['tempmin']}°C\n"
        f"حداکثر: {tomorrow['tempmax']}°C\n"
        f"وضعیت: {tomorrow['conditions']}\n\n"
    )

    # Add rain/snow event
    if next_event:
        cond, t = next_event
        msg += f"🌧️ اولین رویداد: {cond} در ساعت {t}\n\n"

    msg += "🕒 پیش‌بینی ۱۲ ساعت آینده:\n"
    for h in next_hours:
        ts = epoch_to_tehran(h["datetimeEpoch"]).strftime("%H:%M")
        msg += f"{ts} — {h['temp']}°C — {h['conditions']}\n"

    return msg


# ===== TELEGRAM =====
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=payload, timeout=10)


# ===== MAIN =====
def main():
    weather = get_weather()
    aqi = get_tehran_aqi() or "نامشخص"
    msg = format_message(REGION_NAME, weather, aqi)
    send_telegram_message(msg)


if __name__ == "__main__":
    main()
