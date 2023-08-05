import datetime
import time

import requests


def sms_split(text):
    latitude, longitude = False, False
    error_list = []
    sms_content = text.split(' ')
    for n in range(2):
        try:
            n_e_s_w, coordinate = int(sms_content[n][:1]), float(sms_content[n][1:])
        except ValueError:
            error_list.append(n)
        else:
            len_check = sms_content[n].split('.')
            if coordinate < 0 or coordinate > (n * 90 + 90) or len(len_check[0]) < 3:
                error_list.append(n)
            else:
                if n == 0 and n_e_s_w == 0:
                    latitude = coordinate
                elif n == 0 and n_e_s_w == 6:
                    latitude = - coordinate
                elif n == 1 and n_e_s_w == 3:
                    longitude = coordinate
                elif n == 1 and n_e_s_w == 9:
                    longitude = - coordinate
                else:
                    error_list.append(n)

    if len(error_list) > 0:
        for err in error_list:
            if err == 0:
                latitude = 'Incorrect'
            elif err == 1:
                longitude = 'Incorrect'
    coordinates = {'latitude': latitude, 'longitude': longitude}
    try:
        forecast_time = int(sms_content[2])
    except ValueError:
        forecast_time = False
    else:
        if forecast_time < 0 or forecast_time > 144:
            forecast_time = False
    return coordinates, forecast_time


def get_timezone(coordinates):
    lat = coordinates['latitude']
    lng = coordinates['longitude']
    response = requests.get(f'https://api.open-meteo.com/v1/'
                            f'forecast?latitude={lat}&longitude={lng}&'
                            f'timezone=auto')
    utc_offset = response.json()['utc_offset_seconds'] / 3600

    #    response = requests.get(f'http://api.geonames.org/timezoneJSON?lat={lat}&lng={lng}&username=frublev')
    #    gmt = response.json()['gmtOffset']
    return utc_offset


def forecast_time_handling(time_income, hours_plus, utc_offset):
    time_zone_int = -time.timezone / 3600
    hours, minutes = divmod(round(time_income.minute / 60) * 60, 60)
    forecast_time = (time_income + datetime.timedelta(hours=hours) +
                     datetime.timedelta(hours=(hours_plus - time_zone_int))).replace(minute=round(minutes))
    local_time = forecast_time + datetime.timedelta(hours=utc_offset)
    forecast_time = str(forecast_time)[:16].replace(' ', 'T')
    local_time = str(local_time)[5:13].replace('-', '').replace(' ', '_')
    return forecast_time, local_time


def get_forecast(coordinates, forecast_time):
    latitude_f = coordinates['latitude']
    longitude_f = coordinates['longitude']
    response = requests.get(f'https://api.open-meteo.com/v1/forecast?'
                            f'latitude={latitude_f}&longitude={longitude_f}&'
                            f'cell_selection=sea&'
                            f'windspeed_unit=kn&'
                            f'&past_days=1&'
                            f'hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,'
                            f'pressure_msl,'
                            f'windspeed_10m,winddirection_10m,windgusts_10m,'
                            f'precipitation,precipitation_probability,'
                            f'cloudcover,weathercode,visibility')

    response_marine = requests.get(f'https://marine-api.open-meteo.com/v1/marine?'
                                   f'latitude={latitude_f}&longitude={longitude_f}&'
                                   f'cell_selection=sea&'
                                   f'hourly=wave_height,wave_direction,wave_period')

    forecast = response.json()['hourly']
    forecast_marine = response_marine.json()['hourly']
    time_index = forecast['time'].index(forecast_time)
    outcome_data = {
        'V': forecast['visibility'][time_index],
        'WC': forecast['weathercode'][time_index],
        'T': forecast['temperature_2m'][time_index],
        'WD': forecast['winddirection_10m'][time_index],
        'WS': forecast['windspeed_10m'][time_index],
        'WG': forecast['windgusts_10m'][time_index],
        'P': [forecast['pressure_msl'][time_index - 7],
              forecast['pressure_msl'][time_index - 6],
              forecast['pressure_msl'][time_index - 5],
              forecast['pressure_msl'][time_index - 4],
              forecast['pressure_msl'][time_index - 3],
              forecast['pressure_msl'][time_index - 2],
              forecast['pressure_msl'][time_index - 1],
              forecast['pressure_msl'][time_index]],
        'H': forecast['relativehumidity_2m'][time_index],
        'RP': forecast['dewpoint_2m'][time_index],
        'C': forecast['cloudcover'][time_index],
        'WaH': forecast_marine['wave_height'][time_index],
        'WaD': forecast_marine['wave_direction'][time_index],
        'WaP': forecast_marine['wave_period'][time_index],
    }
    print(outcome_data)
    return outcome_data


def sms_outcome(request):
    time_now = datetime.datetime.fromtimestamp(request['time'])
    lat_lng, h_plus = sms_split(request['income_sms'])
    utc_offset = get_timezone(lat_lng)
    utc, local_t = forecast_time_handling(time_now, h_plus, utc_offset)
    forecast = get_forecast(lat_lng, utc)
    outcome_sms = local_t
    for key, values in forecast.items():
        if key == 'P':
            forecast_values = ''
            for i in values:
                forecast_values += '-' + str(i)
        else:
            forecast_values = str(values)
        outcome_sms += '/' + key + forecast_values
    print(len(outcome_sms))
    return outcome_sms


# sms_request = {'phone_num': '1234567890',
#                'income_sms': '042.44 3018.65 1',
#                'time': (datetime.datetime.now()+datetime.timedelta(hours=12))}
# print(sms_outcome(sms_request))
