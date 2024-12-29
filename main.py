import dash
from dash import dcc, html, Input, Output, State
import requests
import plotly.graph_objects as go
import pandas as pd
from geopy.geocoders import Nominatim

# Создание приложения Dash
app = dash.Dash(__name__)
app.title = "Прогноз погоды по маршруту"

# API-ключ OpenWeatherMap (замените на свой ключ)
API_KEY = "your_openweathermap_api_key"
BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"

# Макет приложения
app.layout = html.Div([
    html.H1("Прогноз погоды по маршруту", style={"textAlign": "center"}),

    # Форма для ввода маршрута
    html.Div([
        html.Label("Начальная точка:"),
        dcc.Input(id="start-point", type="text", placeholder="Введите начальную точку", style={"marginRight": "10px"}),

        html.Label("Конечная точка:"),
        dcc.Input(id="end-point", type="text", placeholder="Введите конечную точку"),

        html.Button("Добавить промежуточную точку", id="add-stop", n_clicks=0, style={"marginLeft": "10px"}),

        html.Div(id="stops-container", children=[]),
    ], style={"marginBottom": "20px"}),

    # Переключатель временных интервалов
    html.Label("Выберите временной интервал:", style={"fontWeight": "bold"}),
    dcc.Dropdown(
        id="time-interval",
        options=[
            {"label": "Сегодня", "value": "today"},
            {"label": "3 дня", "value": "3days"},
            {"label": "Неделя", "value": "week"}
        ],
        value="today",
        style={"width": "50%", "marginBottom": "20px"}
    ),

    # Кнопка для запуска анализа
    html.Button("Показать прогноз и маршрут", id="show-results", n_clicks=0, style={"marginBottom": "20px"}),

    # График
    dcc.Graph(id="weather-graph"),

    # Карта маршрута
    html.Div([
        html.H3("Маршрут на карте:"),
        dcc.Graph(id="route-map"),
    ], style={"height": "500px", "marginTop": "20px"}),
])


# Функция для получения данных о погоде
def get_weather_data(location):
    params = {
        "q": location,
        "appid": API_KEY,
        "units": "metric"
    }
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if "list" in data:
            return data
        else:
            return None
    except requests.RequestException as e:
        print(f"Ошибка при запросе данных для {location}: {e}")
        return None



def get_coordinates(location):
    geolocator = Nominatim(user_agent="weather_route_app")
    try:
        location_data = geolocator.geocode(location)
        return (location_data.latitude, location_data.longitude)
    except:
        return None


# Callback для динамического добавления полей маршрута
@app.callback(
    Output("stops-container", "children"),
    Input("add-stop", "n_clicks"),
    State("stops-container", "children")
)
def add_stop(n_clicks, children):
    new_input = dcc.Input(
        id={"type": "stop", "index": n_clicks},
        type="text",
        placeholder=f"Промежуточная точка {n_clicks}",
        style={"marginRight": "10px", "marginTop": "10px"}
    )
    children.append(new_input)
    return children


# Callback для обновления графика погоды
@app.callback(
    Output("weather-graph", "figure"),
    [
        Input("show-results", "n_clicks")  # Зависимость от кнопки
    ],
    [
        State("start-point", "value"),
        State("end-point", "value"),
        State("time-interval", "value"),
        State({"type": "stop", "index": dash.dependencies.ALL}, "value")
    ]
)
def update_weather_graph(n_clicks, start_point, end_point, interval, stops):
    if n_clicks == 0 or not start_point or not end_point:
        return go.Figure()

    locations = [start_point] + [stop for stop in stops if stop] + [end_point]
    weather_data = []

    for location in locations:
        data = get_weather_data(location)
        if data and "list" in data:
            for item in data["list"]:
                weather_data.append({
                    "location": location,
                    "time": item["dt_txt"],
                    "temperature": item["main"]["temp"],
                    "weather": item["weather"][0]["description"]
                })

    if not weather_data:
        # Если данных нет, возвращаем пустой график с предупреждением
        return go.Figure().update_layout(title="Данные о погоде не найдены")

    df = pd.DataFrame(weather_data)
    fig = go.Figure()

    for location in df["location"].unique():
        filtered = df[df["location"] == location]
        fig.add_trace(go.Scatter(
            x=filtered["time"],
            y=filtered["temperature"],
            mode="lines+markers",
            name=location
        ))

    fig.update_layout(title="Прогноз температуры", xaxis_title="Время", yaxis_title="Температура (°C)")
    return fig



# Callback для обновления карты маршрута
@app.callback(
    Output("route-map", "figure"),
    [
        Input("show-results", "n_clicks")  # Зависимость от кнопки
    ],
    [
        State("start-point", "value"),
        State("end-point", "value"),
        State({"type": "stop", "index": dash.dependencies.ALL}, "value")
    ]
)
def update_map(n_clicks, start_point, end_point, stops):
    if n_clicks == 0 or not start_point or not end_point:
        return go.Figure()

    locations = [start_point] + [stop for stop in stops if stop] + [end_point]
    coordinates = []

    for location in locations:
        coords = get_coordinates(location)
        if coords:
            coordinates.append(coords)

    fig = go.Figure()

    if coordinates:
        lats, lons = zip(*coordinates)
        fig.add_trace(go.Scattermapbox(
            lat=lats,
            lon=lons,
            mode="markers+lines",
            marker=dict(size=10),
            text=locations,
        ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=lats[0], lon=lons[0]),
            zoom=5
        ),
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    return fig


# Запуск приложения
if __name__ == "__main__":
    app.run_server(debug=True)