import requests
import pandas as pd
import polyline
from dotenv import load_dotenv
import os
import urllib3

urllib3.disable_warnings()
load_dotenv()

auth_url = "https://www.strava.com/oauth/token"
activities_url = "https://www.strava.com/api/v3/athlete/activities"

payload = {
    'client_id': os.getenv('CLIENT_ID'),
    'client_secret': os.getenv('CLIENT_SECRET'),
    'refresh_token': os.getenv('REFRESH_TOKEN'),
    'grant_type': "refresh_token",
    'scope': "activity:read_all",
    'f': 'json'
}

response = requests.post(auth_url, data=payload, verify=False)
access_token = response.json()['access_token']
header = {'Authorization': 'Bearer ' + access_token}
param = {'per_page': 200, 'page': 1}

dataset = requests.get(activities_url, headers=header, params=param).json()

activities = []
for activity in dataset:
    if activity["type"] == "Run":
        polyline_data = activity.get("map", {}).get("summary_polyline")
        coordinates = polyline.decode(polyline_data)
        activities.append({
            "name": activity["name"],
            "distance_km": activity["distance"] / 1000, 
            "moving_time": activity["moving_time"] / 60,
            "elevation_gain": activity["total_elevation_gain"],
            "date": activity["start_date_local"],
            "coordinates": coordinates
        })

activities_df = pd.DataFrame(activities)
activities_df.to_csv("data/activities.csv", index=False)
print("Success!")
