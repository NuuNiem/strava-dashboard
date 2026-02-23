import requests
import pandas as pd
import polyline as polyline_lib
from dotenv import load_dotenv
import os

load_dotenv()

auth_url = "https://www.strava.com/oauth/token"
activities_url = "https://www.strava.com/api/v3/athlete/activities"

payload = {
    "client_id": os.getenv("CLIENT_ID"),
    "client_secret": os.getenv("CLIENT_SECRET"),
    "refresh_token": os.getenv("REFRESH_TOKEN"),
    "grant_type": "refresh_token",
    "scope": "activity:read_all",
    "f": "json",
}

response = requests.post(auth_url, data=payload)
response.raise_for_status()
access_token = response.json()["access_token"]
header = {"Authorization": "Bearer " + access_token}

activities = []
page = 1
while True:
    param = {"per_page": 200, "page": page}
    dataset = requests.get(activities_url, headers=header, params=param).json()
    if not isinstance(dataset, list) or not dataset:
        break
    for activity in dataset:
        if activity.get("sport_type") == "Run" or activity.get("type") == "Run":
            polyline_data = activity.get("map", {}).get("summary_polyline")
            if not polyline_data:
                continue
            coordinates = polyline_lib.decode(polyline_data)
            activities.append(
                {
                    "name": activity["name"],
                    "distance_km": activity["distance"] / 1000,
                    "moving_time": activity["moving_time"] / 60,
                    "elevation_gain": activity["total_elevation_gain"],
                    "date": activity["start_date_local"],
                    "average_speed": activity.get("average_speed", 0),
                    "coordinates": coordinates,
                }
            )
    page += 1

activities_df = pd.DataFrame(activities)
activities_df.to_csv("data/activities.csv", index=False)
print(f"Success! Fetched {len(activities)} runs.")
