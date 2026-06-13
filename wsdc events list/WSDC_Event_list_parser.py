import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import pycountry
from pycountry_convert import country_name_to_country_alpha2, country_alpha2_to_continent_code
from geopy.geocoders import Nominatim
import schedule
import time
import json


# def extract_event_list_info():

url = "https://www.worldsdc.com/events/" 
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")
table = soup.find("table")
data = []

# Извлекаем заголовки таблицы
head = table.find("thead")
headers = [header.text for header in head.find_all("th")]

# Добавляем 'Canceled' и 'Link' в список заголовков
headers.extend(['canceled', 'link'])

# Проходим по всем строкам таблицы
for row in table.find_all("tr")[1:]:
    # Создаем пустой список для хранения данных из одной строки
    row_data = []
    # Проходим по всем ячейкам строки
    for cell in row.find_all("td"):
        # Если в ячейке есть элемент img, извлекаем значение атрибута data-flag
        img = cell.find("img")
        if img and 'data-flag' in img.attrs:
            row_data.append(img['data-flag'])
        else:
            # Добавляем текст из ячейки в список row_data
            row_data.append(cell.text)
    # Проверяем, есть ли у строки класс 'event-canceled'
    if 'event-canceled' in row.attrs.get('class', []):
        row_data.append(True)
    else:
        row_data.append(False)
    # Извлекаем ссылку на страницу события
    event_link = row.find("div", class_="event_name").find("a")['href']
    row_data.append(event_link)
    # Добавляем список row_data в список data
    data.append(row_data)

# Создаем датафрейм из списка списков, указывая названия столбцов
df = pd.DataFrame(data, columns=headers)

# Функция для преобразования даты в формат DD.MM.YYYY
def format_date(date_str, year):
    try:
        return datetime.strptime(date_str + ' ' + year, '%b %d %Y').strftime('%d.%m.%Y')
    except ValueError:
        return None

# Функция для разделения даты на год и дату начала
def split_date(date_str):
    try:
        start_date, end_date = date_str.split(' - ')
        if ',' in end_date:
            end_date, year = end_date.split(', ')
        elif ' ' in start_date:
            start_date, year = start_date.rsplit(' ', 1)
        else:
            year = start_date.rsplit(' ', 1)[1]
        # Преобразуем даты в формат DD.MM.YYYY
        start_date = format_date(start_date, year)
        end_date = format_date(end_date, year)
        return pd.Series([year, start_date, end_date])
    except ValueError:
        return pd.Series([None, None, None])

# Применяем функцию к столбцу 'Date'
df[['year', 'start_date', 'end_date']] = df['Date'].apply(split_date)
# Удаляем столбец 'End_date' потому что формат дат слишком разный
df = df.drop(columns=['end_date'])

# Функция для разделения названия события, статуса подтверждения и типа события
def split_event_name(event_name):
    if 'Registry Event' in event_name:
        status_event = 'Registry Event'
        event_name = event_name.replace('Registry Event', '')
    elif 'Trial Event' in event_name or '(Trial Event)' in event_name:
        status_event = 'Trial Event'
        event_name = event_name.replace('(Trial Event)', '')
        event_name = event_name.replace('Trial Event', '')    
    else:
        status_event = ''
    if '(Unconfirmed)' in event_name or '(unconirmed)' in event_name or ' Unconfirmed)'in event_name or '(unconfirmed)' in event_name or '(Unfonfirmed)' in event_name:
        event_name = event_name.replace('(Unconfirmed)', '')
        event_name = event_name.replace('(unconirmed)', '')
        event_name = event_name.replace('(unconfirmed)', '')
        event_name = event_name.replace(' Unconfirmed)', '')
        event_name = event_name.replace('(Unfonfirmed)', '')
        confirmed = False
    else:
        confirmed = True
    return pd.Series([event_name.strip(), confirmed, status_event])

# Применяем функцию к столбцу 'Event Name'
df[['Event Name', 'confirmed', 'status_event']] = df['Event Name'].apply(split_event_name)

df.loc[df['Event Location'] == 'Windsor/Slough, London', 'Country'] = 'GBR'
df['Country'] = df['Country'].replace('', 'RUS')

# Функция для преобразования сокращенного обозначения страны в полное название
def convert_country_code_to_name(code):
    try:
        return pycountry.countries.get(alpha_3=code).name
    except AttributeError:
        return None

# Применяем функцию к столбцу 'Country'
df['Country'] = df['Country'].apply(convert_country_code_to_name)

df.rename(columns={'Date': 'original_date', 'Event Name': 'event_name', 'Event Location' : 'event_location', 'Country' : 'country'}, inplace=True)
df = df.reindex(columns=['year', 
                            'start_date', 
                            'original_date',
                            'event_name',
                            'status_event',
                            'event_location',
                            'country', 
                            'confirmed',
                            'canceled',
                            'link'])

df.loc[df['event_location'] == 'Ljubljana, Slovenia', 'country'] = 'Slovenia'

# Функция для преобразования сокращенного обозначения страны в полное название
def create_continent(country):
    try:
        if country:
            country_code = country_name_to_country_alpha2(country, cn_name_format="default")
            continent_name = country_alpha2_to_continent_code(country_code)
            return continent_name
        else:
            return 'Invalid Country'
    except AttributeError:
        return 'Attribute Error Occurred'

# Применяем функцию к столбцу 'Country'
df['continent'] = df['country'].apply(create_continent)


# Создаем экземпляр геокодера
geolocator = Nominatim(user_agent="my_geocoder")

df.loc[df['event_name'] == 'Avignon City Swing', 'event_location'] = 'Gard, France'
df.loc[df['event_name'] == 'Avignon City Swing', 'status_event'] = 'Registry Event'
df.loc[df['event_name'] == 'Avignon City Swing', 'country'] = 'France'
df.loc[df['event_name'] == 'Asia West Coast Swing Open', 'event_location'] = 'Singapore'
df.loc[df['event_name'] == 'Sea Dance Fest', 'event_location'] = 'Anapa, Russia'
df.loc[df['event_name'] == 'Swing Fling', 'event_location'] = 'Herndon, VA'
df.loc[df['event_name'] == 'Swingtzerland', 'event_location'] = 'Zürich, Switzerland'
df.loc[df['event_location'] == 'Zurich,  Swintzerland', 'event_location'] = 'Zürich, Switzerland'
df.loc[df['event_name'] == 'Easter Swing', 'event_location'] = 'Seattle, WA'
df.loc[df['event_location'] == 'Kraków, malopolska, Polska', 'event_location'] = 'Kraków, Poland'
df.loc[df['event_location'] == 'LYON France, Rhones, France', 'event_location'] = 'Lyon, Rhone, France'
df.loc[df['event_location'] == 'Bonn, Nordrhein-Westphalen, Germany', 'event_location'] = 'Bonn, Germany'
df.loc[df['event_location'] == 'LYON, Rhones, France', 'event_location'] = 'Lyon, Rhone, France'


cache = {}

# Функция для получения координат по названию локации
def get_coordinates(location):
    """
    Получает координаты для указанного местоположения с использованием Nominatim.
    
    Args:
        location (str): Название места (например, "Portland, OR, USA").
    
    Returns:
        tuple: (широта, долгота) или None, если координаты не найдены.
    """
    if location in cache:  # Проверка кэша
        return cache[location]
    
    try:
        location_info = geolocator.geocode(location, timeout=10)  # Запрос координат
        if location_info:
            coordinates = (location_info.latitude, location_info.longitude)
            cache[location] = coordinates  # Сохранение в кэш
            return coordinates
        else:
            print(f"Coordinates not found for {location}.")
            return None
    except Exception as e:
        print(f"Error fetching coordinates for {location}: {e}")
        return None

# Применяем функцию к столбцу "event_location" и создаем новые столбцы "latitude" и "longitude"
df["Coordinates"] = df["event_location"].apply(get_coordinates)

# Разделяем координаты на два столбца
df[["Latitude", "Longitude"]] = df["Coordinates"].apply(pd.Series)

# Удаление временного столбца с координатами, если нужно
df.drop(columns=["Coordinates"], inplace=True)

# Создаем словарь с координатами для мест, которые не удалось найти
additional_coordinates = {
    "Sesto San Giovani, Italy": (45.5328245, 9.2256875),
    "Old Windsor, Berkshire, Engand": (51.46225, -0.58059),
    "Bracknell, Berkshire, United Kingdom": (51.416, -0.749),
    "Westminster, Col": (39.8366500, -105.0372000),
    "Mansfield, MA" : (42.0333333, -71.2194444), 
    'Helsinki, Finland': (60.1695200, 24.9354500),
    'Philadelphia PA, Delaware, New Castle' : (39.578330, -75.638980),
    'San Francisco, CA, San Mateo' : (37.554169, -122.313057),
    'Seatttle, WA, King' : (47.608013, -122.335167),
    'Stockholm-Uppsala, Uppland, Uppland' : (59.947878, 18.062112),
    'Singapore' : (1.28967, 103.85),
    'Auckland, North Island, New Zealand' : (-36.8485, 174.763)
    # Другие местоположения...
}

#правим некорректные страны и континенты
df.loc[df['event_location'] == 'Slovenia', 'country'] = 'Slovenia'
df.loc[df['event_location'] == 'Kuala Lumpur, Selangor, Malaysia', 'country'] = 'Malaysia'
df.loc[df['event_location'] == 'Slovenia', 'continent'] = 'EU'
df.loc[df['event_location'] == 'Kuala Lumpur, Selangor, Malaysia', 'continent'] = 'AS'
df.loc[df['country'] == 'Russian Federation', 'country'] = 'Russia'
df.loc[df['country'] == 'Korea, Republic of', 'country'] = 'Republic of Korea'
df.loc[df['event_location'] == 'Dundalk, Ireland', 'continent'] = 'EU'
df.loc[df['event_location'] == 'Dundalk, Ireland', 'country'] = 'Ireland'



# Добавляем координаты в датафрейм
for location, coords in additional_coordinates.items():
    df.loc[df["event_location"] == location, ["Latitude", "Longitude"]] = coords
    
# Словарь для хранения предыдущих смещений
offset_dict = {}

# Функция для добавления смещения координат
def add_offset(row):
    offset = 0.06  # Небольшое смещение (можете настроить под свои нужды)
    key = (row['Latitude'], row['Longitude'])
    
    if key in offset_dict:
        offset_value = offset_dict[key]
        row['Latitude'] += offset_value
        row['Longitude'] += offset_value
        offset_dict[key] += offset  # Увеличиваем смещение для нового события с такими координатами
    else:
        offset_dict[key] = offset
    
    return row

# Применяем функцию к датафрейму
df = df.apply(add_offset, axis=1)

df1 = pd.read_csv('Date 2019-2030.csv')

# Преобразование столбца start_date к типу datetime
df['start_date'] = pd.to_datetime(df['start_date'], format='%d.%m.%Y')
df1['Date'] = pd.to_datetime(df1['Date'], format='%d.%m.%Y')

# Объединение по столбцу даты
merged_df = pd.merge(df1, df, left_on='Date', right_on='start_date', how='left')

# Фильтрация по периоду
min_year = df['start_date'].dt.year.min()
max_year = df['start_date'].dt.year.max()
df1 = merged_df[(merged_df['Date'] >= f'{min_year}-01-01') & (merged_df['Date'] <= f'{max_year}-12-31')]

#df.to_csv('event_list.csv', index=False)
df1.to_csv('event_list_for_calendar.csv', index=False)

# def main():
    
#     # schedule.every(4).seconds.do(extract_event_list_info)
#     # schedule.every(5).minutes.do(extract_event_list_info)
#     schedule.every(2).hours.do(extract_event_list_info)
#     # schedule.every().day.at('17:03').do(extract_event_list_info)
#     # schedule.every().thursday.do(extract_event_list_info)
#     # schedule.every().friday.at('23:45').do(extract_event_list_info)
    
#     while True:
#         schedule.run_pending()
        
# if __name__ == '__main__':
#     main()
