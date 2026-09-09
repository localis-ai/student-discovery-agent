from datetime import timedelta

from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.common.utils.logging import logger
from app.modules.users.utils.auth import create_access_token


def admin_login(username: str, password: str) -> dict:
    """
    Authenticate admin with username and password from config.
    Returns JWT access token if credentials match.
    """
    logger.info(f"Admin service: admin_login attempt for username={username}")

    # Verify credentials against config
    if username != settings.ADMIN_USERNAME or password != settings.ADMIN_PASSWORD:
        logger.warning(f"Admin service: invalid credentials for username={username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # Create JWT token for admin
    # Using a special admin identifier in the token payload
    token_data = {"sub": "admin", "admin": True}
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    logger.info(f"Admin service: admin_login successful for username={username}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
    }
