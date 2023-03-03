SMS = '042.44 3018.65 1'


def sms_split(text):
    latitude, longitude = False, False
    error_list = []
    sms_content = SMS.split(' ')
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
    return coordinates


print(sms_split(SMS))
