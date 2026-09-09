from fastapi import APIRouter

from app.modules.admin.schemas.auth_admin import (
    AdminLoginRequest,
    AdminTokenResponse,
)
from app.modules.admin.services.auth_admin import admin_login

router = APIRouter(prefix="/admin/auth", tags=["Admin-Auth"])


@router.post("/login", response_model=AdminTokenResponse)
def login(credentials: AdminLoginRequest) -> AdminTokenResponse:
    """
    Admin login endpoint.
    Accepts username and password, returns JWT access token.

    Credentials are verified against ADMIN_USERNAME and ADMIN_PASSWORD in config.
    """
    token_data = admin_login(credentials.username, credentials.password)

    return AdminTokenResponse(access_token=token_data["access_token"], token_type=token_data["token_type"], expires_in=token_data["expires_in"])
