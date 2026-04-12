import json
import os

import requests

url = os.environ.get('ROUTERAI_API_URL', 'https://routerai.ru/api/v1') + '/models'
api_key = os.environ.get('ROUTERAI_API_KEY', '')

if not api_key:
    raise OSError(
        'ROUTERAI_API_KEY environment variable is not set. '
        'Please export it before running this script.'
    )

headers = {'Authorization': f'Bearer {api_key}'}

try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        models = response.json()
        print(json.dumps(models, indent=2))
    else:
        print(f'Error {response.status_code}: {response.text}')
except Exception as e:
    print(f'Exception: {e}')
