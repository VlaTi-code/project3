import dash
from dash import dcc, html, Input, Output, State
import requests
import plotly.graph_objects as go
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Создание приложения Dash
app = dash.Dash(__name__)
app.title = "Прогноз погоды по маршруту"

# API-ключ OpenWeatherMap (замените на свой ключ)
API_KEY = "b56afef8fa4720a9442fe43746d97a6d"
BASE_URL = "http://api.openweathermap.org/data/2.5/forecast"

# Макет приложения
app.layout = html.Div([
    html.Div(
        html.H1("Прогноз погоды по маршруту"),
        className="header"
    ),

    html.Div([
        html.Div([
            html.Label("Начальная точка:"),
            dcc.Input(id="start-point", type="text", placeholder="Введите начальную точку", className="form-control"),

            html.Label("Конечная точка:"),
            dcc.Input(id="end-point", type="text", placeholder="Введите конечную точку", className="form-control"),

            html.Button("Добавить промежуточную точку", id="add-stop", n_clicks=0, className="btn btn-primary"),

            html.Div(id="stops-container", children=[]),
        ], className="form-container"),

        html.Div([
            html.Label("Выберите временной интервал:"),
            dcc.Dropdown(
                id="time-interval",
                options=[
                    {"label": "Сегодня", "value": "today"},
                    {"label": "3 дня", "value": "3days"},
                    {"label": "Неделя", "value": "week"}
                ],
                value="today",
                className="form-control"
            ),
        ], className="dropdown-container"),
    ], className="input-section"),

    html.Button("Показать прогноз и маршрут", id="show-results", n_clicks=0, className="btn btn-success"),

    html.Div([
        html.Div([
            html.H3("Прогноз температуры:"),
            dcc.Graph(id="weather-graph"),
        ], className="graph-container"),

        html.Div([
            html.H3("Маршрут на карте:"),
            dcc.Graph(id="route-map"),
        ], className="graph-container"),
    ], className="result-section"),
], className="main-container")


# Функция для получения данных о погоде
def get_weather_data(location):
    coords = get_coordinates(location)
    if not coords:
        print(f"Не удалось получить координаты для {location}.")
        return None

    lat, lon = coords
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric"
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=10)  # Увеличен тайм-аут
        response.raise_for_status()
        data = response.json()
        return data if "list" in data else None
    except requests.RequestException as e:
        print(f"Ошибка при запросе данных для {location} (координаты {lat}, {lon}): {e}")
        return None


def get_coordinates(location):
    geolocator = Nominatim(user_agent="weather_route_app", timeout=10)  # Увеличен тайм-аут
    try:
        location_data = geolocator.geocode(location)
        return (location_data.latitude, location_data.longitude) if location_data else None
    except GeocoderTimedOut:
        print(f"Тайм-аут при получении координат для {location}. Попробуйте снова.")
        return None
    except Exception as e:
        print(f"Ошибка при получении координат для {location}: {e}")
        return None


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
        className="form-control",
        style={"marginTop": "10px"}
    )
    children.append(new_input)
    return children


@app.callback(
    Output("weather-graph", "figure"),
    [Input("show-results", "n_clicks")],
    [State("start-point", "value"), State("end-point", "value"),
     State("time-interval", "value"),
     State({"type": "stop", "index": dash.dependencies.ALL}, "value")]
)
def update_weather_graph(n_clicks, start_point, end_point, interval, stops):
    if n_clicks == 0 or not start_point or not end_point:
        return go.Figure().update_layout(title="Введите точки маршрута")

    locations = [start_point] + [stop for stop in stops if stop] + [end_point]
    weather_data = []

    for location in locations:
        data = get_weather_data(location)
        if data:
            for item in data["list"]:
                weather_data.append({
                    "location": location,
                    "time": item["dt_txt"],
                    "temperature": item["main"]["temp"],
                    "weather": item["weather"][0]["description"]
                })

    if not weather_data:
        return go.Figure().update_layout(title="Данные о погоде не найдены")

    df = pd.DataFrame(weather_data)
    fig = go.Figure()
    for location in df["location"].unique():
        filtered = df[df["location"] == location]
        fig.add_trace(go.Scatter(
            x=filtered["time"], y=filtered["temperature"],
            mode="lines+markers", name=location
        ))

    fig.update_layout(title="Прогноз температуры", xaxis_title="Время", yaxis_title="Температура (°C)")
    return fig


@app.callback(
    Output("route-map", "figure"),
    [Input("show-results", "n_clicks")],
    [State("start-point", "value"), State("end-point", "value"),
     State({"type": "stop", "index": dash.dependencies.ALL}, "value")]
)
def update_map(n_clicks, start_point, end_point, stops):
    if n_clicks == 0 or not start_point or not end_point:
        return go.Figure().update_layout(title="Введите точки маршрута")

    locations = [start_point] + [stop for stop in stops if stop] + [end_point]
    coordinates = [get_coordinates(location) for location in locations]
    coordinates = [coord for coord in coordinates if coord]

    if not coordinates:
        return go.Figure().update_layout(title="Маршрут не найден")

    lats, lons = zip(*coordinates)
    fig = go.Figure()
    fig.add_trace(go.Scattermapbox(
        lat=lats, lon=lons, mode="markers+lines",
        marker=dict(size=10), text=locations
    ))

    fig.update_layout(
        mapbox=dict(style="open-street-map", center=dict(lat=lats[0], lon=lons[0]), zoom=5),
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    return fig


if __name__ == "__main__":
    app.run_server(debug=True)
