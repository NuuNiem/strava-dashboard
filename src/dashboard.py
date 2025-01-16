import dash
from dash import html, dcc, Input, Output
import dash_leaflet as dl
import pandas as pd
import dash_bootstrap_components as dbc
import flask
import os


def load_data():
    activities = pd.read_csv("data/activities.csv")
    activities["date"] = pd.to_datetime(activities["date"])
    activities["coordinates"] = activities["coordinates"].apply(eval)
    return activities

activities = load_data()

def calculate_statistics(activities):
    goal_distance_km = 1000
    total_distance_km = activities["distance_km"].sum()
    goal_progress = (total_distance_km / goal_distance_km) * 100

    longest_run = activities["distance_km"].max()
    highest_elevation = activities["elevation_gain"].max()

    pb_5km = activities[activities["distance_km"] >= 5].nsmallest(1, "moving_time")["moving_time"].values[0]
    pb_10km = activities[activities["distance_km"] >= 10].nsmallest(1, "moving_time")["moving_time"].values[0]
    pb_half_marathon = activities[activities["distance_km"] >= 21.0975].nsmallest(1, "moving_time")["moving_time"].values[0]
    pb_marathon = activities[activities["distance_km"] >= 42.195].nsmallest(1, "moving_time")["moving_time"].values[0]
    average_pace = (activities["moving_time"].sum() / activities["distance_km"].sum()) if activities["distance_km"].sum() > 0 else 0

    month_with_most_activities = activities.resample('M', on='date').size().idxmax().strftime('%B %Y')
    most_activities_count = activities.resample('M', on='date').size().max()

    return {
        "goal_distance_km": goal_distance_km,
        "total_distance_km": total_distance_km,
        "goal_progress": goal_progress,
        "longest_run": longest_run,
        "highest_elevation": highest_elevation,
        "pb_5km": pb_5km,
        "pb_10km": pb_10km,
        "pb_half_marathon": pb_half_marathon,
        "pb_marathon": pb_marathon,
        "average_pace": average_pace,
        "month_with_most_activities": month_with_most_activities,
        "most_activities_count": most_activities_count
    } 

stats = calculate_statistics(activities)

def format_time(minutes):
    hours = minutes // 60
    minutes = minutes % 60
    return "{}h {}m".format(int(hours), int(minutes))

stats["pb_5km"] = format_time(stats["pb_5km"])
stats["pb_10km"] = format_time(stats["pb_10km"])
stats["pb_half_marathon"] = format_time(stats["pb_half_marathon"])
stats["pb_marathon"] = format_time(stats["pb_marathon"])

def create_map_layers(min_distance):
    layers = []
    filtered_activities = activities[activities["distance_km"] >= min_distance]
    for _, row in filtered_activities.iterrows():
        if row["coordinates"]:
            lat_lng = [{"lat": coord[0], "lng": coord[1]} for coord in row["coordinates"]]
            layers.append(
                dl.Polyline(
                    positions=lat_lng,
                    color="red",
                    weight=2,
                    opacity=0.7,
                    children=[
                        dl.Tooltip(row["name"]),
                        dl.Popup(
                            "Distance: {:.2f} km, Elevation: {} m".format(row['distance_km'], row['elevation_gain'])
                        ),
                    ],
                )
            )
    return layers

initial_layers = create_map_layers(min_distance=0)

leaflet_map = dl.Map(
    center=(60.192059, 24.945831),
    zoom=10,
    children=[
        dl.TileLayer(),
        dl.LayerGroup(initial_layers, id="layer-group"),
    ],
    style={"width": "100%", "height": "500px", "margin": "auto"},
)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY],
    routes_pathname_prefix='/')

app.title = "Strava Dashboard"

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Strava Dashboard", className="mb-4 header"), width=12)
    ]),
    dbc.Row([
        dbc.Col([
            html.H4("Map of Activities", className="text-center mb-3 header"),
            leaflet_map,
            html.Div([
                html.Label("Filter by Minimum Distance (km):", className="text-light mt-3"),
                dcc.Slider(
                    id="distance-slider",
                    min=0,
                    max=activities["distance_km"].max(),
                    step=1,
                    value=0,
                    marks={int(i): "{} km".format(int(i)) for i in range(0, int(activities["distance_km"].max()) + 1, 10)},
                ),
            ], className="mt-3"),
        ], width=8),
        dbc.Col([
            dbc.Card(
                dbc.CardBody([
                    html.H4("Goal Progress", className="card-title"),
                    html.P("Total Distance: {:.2f} km / 1000 km".format(stats["total_distance_km"]), className="card-text"),
                    dbc.Progress(
                        value=stats["goal_progress"],
                        label="{:.1f}%".format(stats["goal_progress"]),
                        striped=True,
                        animated=True,
                        className="mt-2"
                    )
                ]),
                className="mb-4 shadow-sm card"
            ),
            dbc.Card(
                dbc.CardBody([
                    html.H4("Statistics", className="card-title"),
                    html.P("Number of Runs: {}".format(len(activities)), className="card-text"),
                    html.P("Total Elevation Gain: {:.2f} m".format(activities['elevation_gain'].sum()), className="card-text"),
                    html.P("Average Pace: {:.2f} min/km".format(stats["average_pace"]), className="card-text"),
                    html.P("Month with Most Activities: {} ({} activities)".format(stats["month_with_most_activities"], stats["most_activities_count"]), className="card-text")
                ]),
                className="mb-4 shadow-sm card"
            ),
            dbc.Card(
                dbc.CardBody([
                    html.H4("Best Efforts", className="card-title"),
                    html.P("5km PB: {}".format(stats["pb_5km"]), className="card-text"),
                    html.P("10km PB: {}".format(stats["pb_10km"]), className="card-text"),
                    html.P("Half Marathon PB: {}".format(stats["pb_half_marathon"]), className="card-text"),
                    html.P("Marathon PB: {}".format(stats["pb_marathon"]), className="card-text"),
                    html.P("Longest Run: {:.2f} km".format(stats["longest_run"]), className="card-text"),
                    html.P("Highest Elevation Gain: {:.2f} m".format(stats["highest_elevation"]), className="card-text")
                ]),
                className="mb-4 shadow-sm card"
            ),
        ], width=4),
    ])
], fluid=True)

@app.callback(
    Output("layer-group", "children"),
    Input("distance-slider", "value"),
)
def update_map(min_distance):
    return create_map_layers(min_distance)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run_server(debug=False, host="0.0.0.0", port=port)