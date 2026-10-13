from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.core.security import get_totp_uri
from app.api.deps import get_current_user

router = APIRouter()


@router.post("/register")
async def register(
    pubkey: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: UserRole = Form(UserRole.OWNER),
    db: Session = Depends(get_db)
):
    """Registers new account with credentials and role assignment."""
    try:
        user = AuthService.register_user(db, pubkey, email, password, role)
        totp_uri = get_totp_uri(user.mfa_secret, user.email)
        return {
            "status": "SUCCESS",
            "message": "User registered successfully.",
            "pubkey": user.pubkey,
            "role": user.role.value,
            "totp_uri": totp_uri
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login")
async def login(
    request: Request,
    email_or_pubkey: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Authenticates user credentials and checks if MFA is required."""
    try:
        client_ip = request.client.host if request.client else "127.0.0.1"
        user_agent = request.headers.get("user-agent", "Unknown")
        
        result = AuthService.login(
            db=db,
            email_or_pubkey=email_or_pubkey,
            password=password,
            ip_address=client_ip,
            device_info=user_agent
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/verify-mfa")
async def verify_mfa(
    request: Request,
    user_pubkey: str = Form(...),
    totp_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """Completes MFA authentication step using 6-digit authenticator code."""
    try:
        client_ip = request.client.host if request.client else "127.0.0.1"
        user_agent = request.headers.get("user-agent", "Unknown")
        
        return AuthService.verify_mfa_and_login(
            db=db,
            user_pubkey=user_pubkey,
            totp_code=totp_code,
            ip_address=client_ip,
            device_info=user_agent
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh")
async def refresh_token(
    refresh_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """Exchanges valid refresh token for a new short-lived JWT access token."""
    try:
        return AuthService.refresh_access_token(db, refresh_token)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/mfa/enable")
async def enable_mfa(
    totp_code: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enables MFA for authenticated user after verifying code."""
    try:
        AuthService.enable_mfa(db, current_user.pubkey, totp_code)
        return {"status": "SUCCESS", "message": "MFA enabled successfully."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Returns current user profile and role details."""
    return {
        "pubkey": current_user.pubkey,
        "email": current_user.email,
        "role": current_user.role.value,
        "mfa_enabled": current_user.mfa_enabled,
        "created_at": current_user.created_at
    }