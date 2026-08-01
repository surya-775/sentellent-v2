from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError

from app.core.config import settings


def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        print("JWT decoded:", payload)
        return payload
    except JWTError as e:
        print("JWT ERROR:", repr(e))
        print("JWT_SECRET:", settings.JWT_SECRET[:10] + "...")
        return None
