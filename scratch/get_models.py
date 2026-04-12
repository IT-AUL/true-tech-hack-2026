import json
import os

import requests

# Try multiple env var names to stay compatible with different dev setups
base_url = (
    os.environ.get('ROUTERAI_API_URL')
    or os.environ.get('OPENAI_API_BASE_URL')
    or 'https://routerai.ru/api/v1'
)
api_key = os.environ.get('ROUTERAI_API_KEY') or os.environ.get('OPENAI_API_KEY')

if not api_key:
    raise EnvironmentError(
        'Neither ROUTERAI_API_KEY nor OPENAI_API_KEY environment variable is set. '
        'Please export one of them before running this script.'
    )

url = f'{base_url.rstrip("/")}/models'
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
