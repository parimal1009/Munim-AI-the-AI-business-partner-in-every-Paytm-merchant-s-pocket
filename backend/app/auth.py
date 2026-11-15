"""Demo merchant auth: JWT carrying the merchant id. Every API call derives merchant_id from here."""
from datetime import timedelta

import jwt
from fastapi import Depends, Header

from app.config import get_settings
from app.core import AuthError, utcnow


def issue_token(merchant_id: int) -> str:
    s = get_settings()
    payload = {"sub": str(merchant_id), "exp": utcnow() + timedelta(minutes=s.jwt_ttl_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def current_merchant(authorization: str | None = Header(default=None)) -> int:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Missing bearer token")
    try:
        data = jwt.decode(authorization[7:], get_settings().jwt_secret, algorithms=["HS256"])
        return int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AuthError("Invalid or expired token") from exc


MerchantId = Depends(current_merchant)
