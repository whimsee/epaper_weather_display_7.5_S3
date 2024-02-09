import board, busio, time, alarm, gc, wifi, ssl, adafruit_requests, socketpool, microcontroller, analogio
import waveshare75
import adafruit_ds3231
import adafruit_shtc3
# import adafruit_veml7700
from adafruit_datetime import datetime
import font50
import font76
import font100

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

TIME_API = secrets['time_api']
WEATHER_API = secrets['weather_api']

days = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")

# E-ink pins
reset = board.D1
dc = board.D3
busy = board.D2
cs = board.D4
clk = board.SCK
mosi = board.MOSI
# epd = waveshare75.EPD(reset, dc, busy, cs, clk, mosi)
#### ------- ###

#### i2C and rtc ###
i2c = board.I2C()
rtc_module = adafruit_ds3231.DS3231(i2c)
# veml7700 = adafruit_veml7700.VEML7700(i2c)
sht = adafruit_shtc3.SHTC3(i2c)

#### Light sensor ####
adc = analogio.AnalogIn(board.D5)

def deep_sleep(low_light=False):
    if not low_light:
        time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + (1800 - ((rtc_module.datetime.tm_min % 30) * 60)))
    else:
        time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + (3600 - (rtc_module.datetime.tm_min * 60)))

    alarm.exit_and_deep_sleep_until_alarms(time_alarm)

def wifi_connect(retries=3):
    i = 0
    print("Connecting to %s"%secrets["ssid"])
    while True:
        try:
            wifi.radio.connect(secrets["ssid"], secrets["password"])
            print("Connected to %s!"%secrets["ssid"])
            return True
        except ConnectionError as e:
            print("Failed to connect, retrying\n", e)
            if i < 3:
                i += 1
                continue
            else:
                print("No internet. Sleeping")
                deep_sleep()

# JSON -- Time
def get_time(retries=3):
    i = 0
    while True:
        try:
            print("Fetching json from", TIME_API)
            with requests.get(TIME_API) as response:
                time_json = response.json()
            break
        except OSError as e:
            print("Failed to get data, retrying\n", e)
            if i < retries:
                i += 1
                continue
            else:
                print("Continuing")
                return
        except NameError as e:
            print("No Internet", e)
            return


    time_year = time_json['year']
    time_mon = time_json['mon']
    time_mday = time_json['mday']
    time_hour = time_json['hour']
    time_min = time_json['min']
    time_sec = time_json['sec']
    time_wday = time_json['wday']
    time_isdst = time_json['isdst']

    ##### --- RTC module only --- ###
    # The first time you run this code, you must set the time!
    # You must set year, month, date, hour, minute, second and weekday.
    # struct_time order: year, month, day (date), hour, minute, second, weekday , yearday, isdst
    # yearday is not supported, isdst can be set but we don't do anything with it at this time
    set_time = time.struct_time(
        (time_year, time_mon, time_mday, time_hour, time_min, time_sec, time_wday, -1, time_isdst)
    )
    # offset
    offset_time = time.localtime(time.mktime(set_time) + TIME_OFFSET)
    print("Setting time to:", offset_time)
    rtc_module.datetime = offset_time
#     print("Setting time to:", set_time)
#     rtc_module.datetime = set_time

# JSON -- Weather
def get_weather(retries=3):
#     print(rtc_module.datetime.tm_isdst)
    weather_info = {}
    i = 0
    while True:
        try:
            print("Fetching json from", WEATHER_API)
            with requests.get(WEATHER_API) as response:
                weather_json = response.json()
            break
        except OSError as e:
            print("Failed to get data, retrying\n", e)
            if i < retries:
                i += 1
                continue
            else:
                print("Continuing")
                return False
        except NameError as e:
            print("No Internet", e)
            return False

    for x in range(24):
        if rtc_module.datetime.tm_isdst == -1:
            timestamp = int(weather_json['hourly'][x]['dt']) - 28800
        else:
            timestamp = int(weather_json['hourly'][x]['dt']) - 25200
        datetime_obj = datetime.fromtimestamp(timestamp)
        if int(datetime_obj.hour) > 9 and int(datetime_obj.hour) < 20:
            weather_info[datetime_obj.hour] = (datetime_obj.day, weather_json['hourly'][x]['temp'])
            print(datetime_obj)
#     print(weather_info)
    global hour_temp, hour_hum, hour_rain, daily_high, daily_low, daily_pop
    daily_high = {}
    daily_low = {}
    daily_pop = {}

    hour_temp = weather_json['current']['temp']
#     print(hour_temp)
    hour_hum = weather_json['current']['humidity']
#     print(hour_hum)
    for y in range(7):
        daily_high[y] = weather_json['daily'][y]['temp']['max']
        daily_low[y] = weather_json['daily'][y]['temp']['min']
        daily_pop[y] = weather_json['daily'][y]['pop']
#     print(daily_high)
#     print(daily_low)
    rain_sum = []
    for i in range(60):
        try:
            rain_temp = weather_json['minutely'][i]['precipitation']
            rain_sum.append(rain_temp)
        except KeyError:
            pass
    if len(rain_sum) > 0:
        hour_rain = round(sum(rain_sum) / len(rain_sum))
    else:
        hour_rain = False
#     print(hour_rain)

    return weather_info

def buffer_screen():
#     Screen Res: 800x480
    epd.display_string_at(frame_black, 10, 5, "{}".format(wday), font100)
    epd.display_string_at(frame_black, 250, 5, "{}".format(day), font100)
    epd.draw_filled_rectangle(frame_black, 0, 103, 800, 108)
    epd.draw_filled_rectangle(frame_black, 415, 0, 420, 108)
    epd.display_string_at(frame_black, 450, 10, "{}".format(temp), font76)
    epd.draw_filled_circle(frame_black, 570, 10, 6)
    epd.display_string_at(frame_black, 600, 10, "{}%".format(hum), font76)

    Z = 0
    X_OFFSET = 110
    if not weather_info:
        pass
    else:
        epd.display_string_at(frame_black, 150, 130, "{}".format(round(hour_temp)), font76)
        epd.display_string_at(frame_black, 320, 130, "{}%".format(hour_hum), font76)

        if hour_rain:
            epd.display_string_at(frame_black, 580, 130, "{}".format(hour_rain), font76)

        epd.draw_filled_rectangle(frame_black, 50, 225, 750, 228)

        for x in range(7):
            if round(daily_high[x]) < 100:
                epd.display_string_at(frame_black, 35 + (X_OFFSET * x), 260, "{}".format(round(daily_high[x])), font50)
            else:
                epd.display_string_at(frame_black, 16 + (X_OFFSET * x), 260, "{}".format(round(daily_high[x])), font50)
            epd.draw_filled_rectangle(frame_black, 30 + (X_OFFSET * x), 325, 115 + (X_OFFSET * x), 335)
            epd.display_string_at(frame_black, 35 + (X_OFFSET * x), 340, "{}".format(round(daily_low[x])), font50)
            if daily_pop[x] > 0:
                pop_temp = int(daily_pop[x] * 100)
                if pop_temp < 100:
                    epd.display_string_at(frame_black, 35 + (X_OFFSET * x), 410, "{}".format(pop_temp), font50)
                else:
                    epd.display_string_at(frame_black, 55 + (X_OFFSET  * x), 410, "!", font50)


    P_OFFSET = 0
    for p in range(0, rtc_module.datetime.tm_min // 30):
        epd.draw_filled_rectangle(frame_black, 50 + P_OFFSET, 470, 60 + P_OFFSET, 480)
        P_OFFSET += 50


## Setup ##
# print(gc.mem_free())
fb_size = 48000
# Compensation is usually -5 C
TEMP_COMPENSATION = 5
# Use with time.mktime() to offset the time it takes to send SPI instructions.
# Note the wday is off by a day. Account for it in the display code
TIME_OFFSET = 21

try:
    if (wifi_connect()):
        pool = socketpool.SocketPool(wifi.radio)
        requests = adafruit_requests.Session(pool, ssl.create_default_context())
    
    get_time()
    weather_info = get_weather()
    # next_update = int(time.monotonic()) + (3600 - (rtc_module.datetime.tm_min * 60))
except Exception as e:
    print("resetting", e)
    time.sleep(5)
    microcontroller.reset()

gc.collect()

## Main loop ##

while True:
    try:
#         if time.monotonic() > next_update:
#             print("reset microcontroller")
#             microcontroller.reset()

        epd = waveshare75.EPD(reset, dc, busy, cs, clk, mosi)

        light_value = adc.value / 65536 * adc.reference_voltage
#         print("{} / {}".format(adc.value, light_value))
        if light_value == 0:
            raise Exception("Not enough light")

#         print("light:", veml7700.light)
#         if veml7700.light > 0 and veml7700.light < 20:
#             raise Exception("Not enough light")

        frame_black = bytearray(fb_size)
        temperature, relative_humidity = sht.measurements
        temp = int(((temperature - TEMP_COMPENSATION) * 1.8) + 32)
        hum = int(relative_humidity)

        t = rtc_module.datetime

        current_hour = t.tm_hour

        # Compensate wday to account for offsetting date
        wday = days[t.tm_wday + 1 if t.tm_wday < 6 else 0]
        month = t.tm_mon
        day = t.tm_mday

        buffer_screen()

        epd.init()
        epd.display2(frame_black)

        time.sleep(2)
        epd.sleep()
        time.sleep(2)
#         print(60 - int(rtc_module.datetime.tm_sec))
#         print("{} / {}".format(time.monotonic(), next_update))
#         time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + ((3600 - (rtc_module.datetime.tm_min  * 60)) - int(rtc_module.datetime.tm_sec)))
        deep_sleep()
#         time.sleep(60 - int(rtc_module.datetime.tm_sec))
    except Exception as e:
        print(e)
        print("going to sleep")
        epd.init()
        epd.Clear()
        time.sleep(1.5)
        epd.sleep()
        time.sleep(2)
        deep_sleep(True)
#         alarm.light_sleep_until_alarms(time_alarm)
#         time.sleep(3600 - (rtc_module.datetime.tm_min * 60))
#         microcontroller.reset()
#         alarm.exit_and_deep_sleep_until_alarms(alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 10))


