import httpx
from app.config import SUPABASE_URL, SUPABASE_API_KEY
from app.utils.jwt_handler import create_token

async def login_user(email: str, password: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": SUPABASE_API_KEY, "Content-Type": "application/json"},
            json={"email": email, "password": password}
        )
    if response.status_code == 200:
        user_data = response.json()
        token = create_token({"email": email})
        return {"access_token": token, "user": user_data}
    else:
        return {"error": response.json()}
