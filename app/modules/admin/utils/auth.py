import re

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer

from app.core.config import settings
from app.modules.common.utils.logging import logger


class AdminJWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error, scheme_name="AdapterAuth")

    async def __call__(self, request: Request) -> str:
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authentication required")

        # Parse the authorization header
        try:
            scheme, credentials = authorization.split(" ", 1)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication scheme")

        if scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication scheme")

        return credentials


admin_jwt_bearer = AdminJWTBearer()


def verify_admin_token(token: str) -> dict:
    """
    Verify admin JWT token and extract payload.
    Token must have 'admin': True flag.
    """
    try:
        token = re.sub(r"^[Bb]earer\s+", "", token).strip()
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        # Verify token type and admin flag
        token_type = payload.get("type")
        is_admin = payload.get("admin", False)

        if token_type != "access":
            logger.warning("Admin service: Token type invalid")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token type")

        if not is_admin:
            logger.warning("Admin service: Token is not admin token")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

        logger.info("Admin service: Admin token verified successfully")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Admin service: Token expired")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        logger.warning("Admin service: Invalid token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin service: Token verification error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def get_admin_user(token: str = Depends(admin_jwt_bearer)) -> dict:
    """
    Validate admin JWT token and return payload.
    Used as dependency for admin routes to ensure only admin tokens are accepted.
    """
    return verify_admin_token(token)
