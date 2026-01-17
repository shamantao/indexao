import requests
import json
import sys

# Une de vos clés
API_KEY = "AIzaSyCC7XT9DZidz9RCJj6VZnea89oTdB9cs8s"
MODEL = "gemini-flash-latest"

url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

print(f"Testing URL: https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent")

payload = {
    "contents": [{
        "parts": [{"text": "Hello, translate 'testing connection' to French."}]
    }]
}

try:
    response = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}...")
except Exception as e:
    print(f"Error: {e}")

payload = {
    "contents": [{
        "parts": [{"text": "Hello, translate 'testing connection' to French."}]
    }]
}

try:
    print(f"Response: {response.text[:500]}...")
except Exception as e:
    print(f"Error: {e}")
