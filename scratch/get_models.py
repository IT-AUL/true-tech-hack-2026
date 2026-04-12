import requests
import json

url = "https://routerai.ru/api/v1/models"
headers = {
    "Authorization": "Bearer sk-OYLRTbm0t4MeXcMMI7UWRe_zM3EJfS4o"
}

try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        models = response.json()
        print(json.dumps(models, indent=2))
    else:
        print(f"Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
