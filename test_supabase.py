import requests
import json
import os

url = "https://mdvfvtpbwqhccmaarpli.supabase.co/auth/v1/signup"
headers = {
    "apikey": "sb_publishable_m2MXf1_8NyJ5PtiZGIh6sg_Q9hDnJSF",
    "Content-Type": "application/json"
}
data = {
    "email": "testagent@example.com",
    "password": "Password123!"
}
response = requests.post(url, headers=headers, json=data)
print(response.json())
