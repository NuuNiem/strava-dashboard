import ast
import os

import dash
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import pandas as pd
import plotly.graph_objs as go
from dash import Input, Output, dcc, html

STRAVA = "#FC4C02"


def load_data():
    activities = pd.read_csv("data/activities.csv")
    activities["date"] = pd.to_datetime(activities["date"])
    activities["coordinates"] = activities["coordinates"].apply(ast.literal_eval)
    activities["pace"] = activities["moving_time"] / activities["distance_km"]
    return activities


activities = load_data()


def safe_pb(df, min_dist):
    filtered = df[df["distance_km"] >= min_dist]
    if filtered.empty:
        return None
    return filtered.nsmallest(1, "moving_time")["moving_time"].values[0]


def format_time(minutes):
    if minutes is None:
        return "N/A"
    total_seconds = round(minutes * 60)
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}h {mins}m {secs:02d}s"
    return f"{mins}m {secs:02d}s"


def format_pace(pace_min):
    mins = int(pace_min)
    secs = int((pace_min % 1) * 60)
    return f"{mins}:{secs:02d} /km"


def calculate_statistics(df):
    total_distance_km = df["distance_km"].sum()
    average_pace = (
        df["moving_time"].sum() / total_distance_km if total_distance_km > 0 else 0
    )
    monthly = df.resample("ME", on="date").size()
    return {
        "total_distance_km": total_distance_km,
        "total_runs": len(df),
        "total_elevation": df["elevation_gain"].sum(),
        "longest_run": df["distance_km"].max(),
        "highest_elevation": df["elevation_gain"].max(),
        "pb_5km": format_time(safe_pb(df, 5)),
        "pb_10km": format_time(safe_pb(df, 10)),
        "pb_half_marathon": format_time(safe_pb(df, 21.0975)),
        "pb_marathon": format_time(safe_pb(df, 42.195)),
        "average_pace": average_pace,
        "month_with_most_activities": monthly.idxmax().strftime("%B %Y"),
        "most_activities_count": int(monthly.max()),
    }


stats = calculate_statistics(activities)


def get_run_color(distance_km):
    if distance_km < 5:
        return "#60a5fa"
    elif distance_km < 15:
        return STRAVA
    return "#ef4444"


def create_map_layers(min_distance):
    layers = []
    for _, row in activities[activities["distance_km"] >= min_distance].iterrows():
        if not row["coordinates"]:
            continue
        lat_lng = [{"lat": c[0], "lng": c[1]} for c in row["coordinates"]]
        layers.append(
            dl.Polyline(
                positions=lat_lng,
                color=get_run_color(row["distance_km"]),
                weight=2,
                opacity=0.7,
                children=[
                    dl.Tooltip(row["name"]),
                    dl.Popup(
                        f"{row['name']} · {row['distance_km']:.2f} km · "
                        f"{format_time(row['moving_time'])} · {format_pace(row['pace'])} · "
                        f"+{row['elevation_gain']:.0f} m"
                    ),
                ],
            )
        )
    return layers


all_coords = [c for coords in activities["coordinates"] for c in coords]
map_center = (
    (
        sum(c[0] for c in all_coords) / len(all_coords),
        sum(c[1] for c in all_coords) / len(all_coords),
    )
    if all_coords
    else (60.192059, 24.945831)
)

leaflet_map = dl.Map(
    center=map_center,
    zoom=11,
    children=[
        dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"),
        dl.LayerGroup(create_map_layers(0), id="layer-group"),
    ],
    style={"width": "100%", "height": "550px"},
)

monthly_dist = activities.resample("ME", on="date")["distance_km"].sum().reset_index()
monthly_dist["month"] = monthly_dist["date"].dt.strftime("%b %Y")

cumulative = activities.sort_values("date").copy()
cumulative["cumulative_km"] = cumulative["distance_km"].cumsum()

sorted_acts = activities.sort_values("date")

cal = activities.copy()
cal["day"] = cal["date"].dt.normalize()
daily_dist = cal.groupby("day")["distance_km"].sum()
if daily_dist.index.tz is not None:
    daily_dist.index = daily_dist.index.tz_convert(None)

first_day = daily_dist.index.min()
cal_start = first_day - pd.Timedelta(days=first_day.dayofweek)
cal_end = pd.Timestamp.now().normalize()
cal_end = cal_end + pd.Timedelta(days=6 - cal_end.dayofweek)
weeks = pd.date_range(cal_start, cal_end, freq="7D")

dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
z_cal, text_cal = [], []
for dow in range(7):
    row_z, row_text = [], []
    for w in weeks:
        d = w + pd.Timedelta(days=dow)
        dist = float(daily_dist.get(d, 0))
        row_z.append(dist if dist > 0 else None)
        row_text.append(
            f"{d.strftime('%b %d, %Y')}<br>{dist:.1f} km"
            if dist > 0
            else d.strftime("%b %d, %Y")
        )
    z_cal.append(row_z)
    text_cal.append(row_text)

seen_months: set = set()
x_ticks_idx, x_ticks_labels = [], []
for i, w in enumerate(weeks):
    m = w.strftime("%b %Y")
    if m not in seen_months:
        seen_months.add(m)
        x_ticks_idx.append(i)
        x_ticks_labels.append(w.strftime("%b '%y"))

recent = activities.sort_values("date", ascending=False).head(6).copy()

CHART_LAYOUT = dict(
    paper_bgcolor="#1a1a1a",
    plot_bgcolor="#1a1a1a",
    font={"color": "#ccc"},
    margin={"t": 40, "b": 60, "l": 50, "r": 20},
)


def kpi_card(label, value):
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.P(label, className="kpi-label mb-1"),
                    html.H4(value, className="kpi-value mb-0"),
                ]
            ),
            className="kpi-card text-center h-100",
        ),
        xs=6,
        sm=4,
        md=True,
        className="mb-3",
    )


def activity_card(row):
    return dbc.Col(
        dbc.Card(
            [
                dbc.CardHeader(
                    [
                        html.Small(
                            row["date"].strftime("%b %d, %Y"),
                            className="text-muted d-block",
                        ),
                        html.Strong(row["name"], className="activity-name"),
                    ],
                    className="activity-card-header",
                ),
                dbc.CardBody(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span("km", className="stat-unit"),
                                    html.Span(
                                        f"{row['distance_km']:.2f}",
                                        className="stat-val",
                                    ),
                                ],
                                className="stat-block",
                            ),
                            html.Div(
                                [
                                    html.Span("time", className="stat-unit"),
                                    html.Span(
                                        format_time(row["moving_time"]),
                                        className="stat-val",
                                    ),
                                ],
                                className="stat-block",
                            ),
                            html.Div(
                                [
                                    html.Span("pace", className="stat-unit"),
                                    html.Span(
                                        format_pace(row["pace"]), className="stat-val"
                                    ),
                                ],
                                className="stat-block",
                            ),
                            html.Div(
                                [
                                    html.Span("elev", className="stat-unit"),
                                    html.Span(
                                        f"+{row['elevation_gain']:.0f}m",
                                        className="stat-val",
                                    ),
                                ],
                                className="stat-block",
                            ),
                        ],
                        className="stat-row",
                    ),
                    className="p-2",
                ),
            ],
            className="activity-card h-100",
        ),
        xs=12,
        sm=6,
        md=4,
        className="mb-3",
    )


app = dash.Dash(
    __name__, external_stylesheets=[dbc.themes.DARKLY], routes_pathname_prefix="/"
)
app.title = "Strava Dashboard"

avg_pace_str = format_pace(stats["average_pace"])

app.layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.H1("Strava Dashboard", className="mb-0 strava-header"),
                    ],
                    className="py-4",
                ),
                width=12,
            )
        ),
        dbc.Row(
            [
                kpi_card("Total Distance", f"{stats['total_distance_km']:.1f} km"),
                kpi_card("Runs", str(stats["total_runs"])),
                kpi_card("Total Elevation", f"{stats['total_elevation']:.0f} m"),
                kpi_card("Avg Pace", avg_pace_str),
                kpi_card("Longest Run", f"{stats['longest_run']:.2f} km"),
            ],
            className="mb-2",
        ),
        dbc.Row(
            dbc.Col(
                [
                    leaflet_map,
                    html.Div(
                        [
                            html.Span(
                                "● < 5 km",
                                style={"color": "#60a5fa", "marginRight": "16px"},
                            ),
                            html.Span(
                                "● 5–15 km",
                                style={"color": STRAVA, "marginRight": "16px"},
                            ),
                            html.Span("● > 15 km", style={"color": "#ef4444"}),
                        ],
                        className="mt-2 mb-1 text-light",
                        style={"fontSize": "0.85rem"},
                    ),
                ],
                width=12,
            ),
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H5("Statistics", className="card-title"),
                                html.P(
                                    f"Total Runs: {stats['total_runs']}",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"Total Distance: {stats['total_distance_km']:.1f} km",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"Total Elevation: {stats['total_elevation']:.0f} m",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"Avg Pace: {avg_pace_str}",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"Busiest Month: {stats['month_with_most_activities']} "
                                    f"({stats['most_activities_count']} runs)",
                                    className="card-text mb-1",
                                ),
                            ]
                        ),
                        className="h-100 card",
                    ),
                    md=6,
                    className="mb-3",
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H5("Best Efforts", className="card-title"),
                                html.P(
                                    f"5 km: {stats['pb_5km']}",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"10 km: {stats['pb_10km']}",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"Half Marathon: {stats['pb_half_marathon']}",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"Marathon: {stats['pb_marathon']}",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"Longest: {stats['longest_run']:.2f} km",
                                    className="card-text mb-1",
                                ),
                                html.P(
                                    f"Best Elevation: {stats['highest_elevation']:.0f} m",
                                    className="card-text mb-1",
                                ),
                            ]
                        ),
                        className="h-100 card",
                    ),
                    md=6,
                    className="mb-3",
                ),
            ],
            className="mb-2",
        ),
        dbc.Row(
            dbc.Col(
                dbc.Tabs(
                    [
                        dbc.Tab(
                            dcc.Graph(
                                figure={
                                    "data": [
                                        go.Bar(
                                            x=monthly_dist["month"],
                                            y=monthly_dist["distance_km"],
                                            marker_color=STRAVA,
                                            marker_line_width=0,
                                        )
                                    ],
                                    "layout": go.Layout(
                                        title="Monthly Distance (km)",
                                        xaxis={"tickangle": -45},
                                        **CHART_LAYOUT,
                                    ),
                                },
                                config={"displayModeBar": False},
                            ),
                            label="Monthly Distance",
                        ),
                        dbc.Tab(
                            dcc.Graph(
                                figure={
                                    "data": [
                                        go.Scatter(
                                            x=cumulative["date"],
                                            y=cumulative["cumulative_km"],
                                            mode="lines",
                                            line={"color": STRAVA, "width": 2},
                                            fill="tozeroy",
                                            fillcolor="rgba(252,76,2,0.15)",
                                        )
                                    ],
                                    "layout": go.Layout(
                                        title="Cumulative Distance (km)",
                                        **CHART_LAYOUT,
                                    ),
                                },
                                config={"displayModeBar": False},
                            ),
                            label="Cumulative Distance",
                        ),
                        dbc.Tab(
                            dcc.Graph(
                                figure={
                                    "data": [
                                        go.Scatter(
                                            x=sorted_acts["date"],
                                            y=sorted_acts["pace"],
                                            mode="markers",
                                            marker={
                                                "color": STRAVA,
                                                "size": 7,
                                                "opacity": 0.85,
                                            },
                                            text=sorted_acts["name"],
                                            hovertemplate="%{text}<br>%{y:.2f} min/km<extra></extra>",
                                        )
                                    ],
                                    "layout": go.Layout(
                                        title="Pace Over Time (min/km — lower is faster)",
                                        yaxis={"autorange": "reversed"},
                                        **CHART_LAYOUT,
                                    ),
                                },
                                config={"displayModeBar": False},
                            ),
                            label="Pace Over Time",
                        ),
                        dbc.Tab(
                            dcc.Graph(
                                figure={
                                    "data": [
                                        go.Heatmap(
                                            z=z_cal,
                                            x=list(range(len(weeks))),
                                            y=dow_labels,
                                            text=text_cal,
                                            hovertemplate="%{text}<extra></extra>",
                                            colorscale=[
                                                [0, "#2a2a2a"],
                                                [1, STRAVA],
                                            ],
                                            showscale=False,
                                            xgap=2,
                                            ygap=2,
                                        )
                                    ],
                                    "layout": go.Layout(
                                        title="Activity Calendar",
                                        xaxis={
                                            "tickvals": x_ticks_idx,
                                            "ticktext": x_ticks_labels,
                                            "tickangle": -45,
                                            "showgrid": False,
                                        },
                                        yaxis={
                                            "showgrid": False,
                                            "autorange": "reversed",
                                        },
                                        **CHART_LAYOUT,
                                    ),
                                },
                                config={"displayModeBar": False},
                                style={"height": "260px"},
                            ),
                            label="Calendar",
                        ),
                    ]
                ),
                width=12,
            ),
            className="mb-4",
        ),
        dbc.Row(
            dbc.Col(
                [
                    html.H5("Recent Runs", className="strava-header mb-3"),
                    dbc.Row([activity_card(row) for _, row in recent.iterrows()]),
                ],
                width=12,
            ),
            className="mb-5",
        ),
    ],
    fluid=True,
    className="px-4",
)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)
