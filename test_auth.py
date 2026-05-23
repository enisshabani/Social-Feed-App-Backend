import requests

# Let's create a user
res = requests.post("http://127.0.0.1:8000/api/v1/auth/register", json={
    "username": "testuser_403",
    "email": "test403@example.com",
    "password": "password123",
    "display_name": "Test User"
})
print("Register:", res.status_code, res.text)

# Let's login
res = requests.post("http://127.0.0.1:8000/api/v1/auth/login", data={
    "username": "testuser_403",
    "password": "password123"
})
print("Login:", res.status_code, res.text)
if res.status_code == 200:
    token = res.json()["access_token"]
    
    # Let's call /me
    res = requests.get("http://127.0.0.1:8000/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    print("Me:", res.status_code, res.text)
