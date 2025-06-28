import aiohttp
import jwt
from datetime import datetime, timedelta
from config import API_BASE_URL, JWT_SECRET, JWT_ALGORITHM
from bot.database import Database

async def get_user_id_from_token(token: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE_URL}/api/Users/me",
            headers={"Authorization": f"Bearer {token}"}
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data['id']
            raise PermissionError("Invalid token")

def get_user_role(user_id: int) -> str:
    """Get user role from database."""
    db = Database()
    try:
        user = db.get_user(user_id)
        if user:
            return user.get('role', 'user')  # Default to 'user' if role not found
        return None
    finally:
        db.close()

def generate_token(user_id: int, role: str) -> str:
    """Generate JWT token for user."""
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.utcnow() + timedelta(days=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)