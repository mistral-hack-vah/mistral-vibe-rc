import requests

response = requests.get(
    "https://api.mistral.ai/v1/models",
    headers={"Authorization": "Bearer RdWAhW5EOQSfCQXeOlOkmrjsAS6Sw5PS"},
)

print(response.json())
