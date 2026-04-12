import json
import os

import requests

base_url = os.getenv('OPENAI_API_BASE_URL')
api_key = os.getenv('OPENAI_API_KEY')

if not base_url:
    raise RuntimeError('OPENAI_API_BASE_URL is required')

if not api_key:
    raise RuntimeError('OPENAI_API_KEY is required')

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
