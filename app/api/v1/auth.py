from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decoded_token
)
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.schemas.token import Token, RefreshTokenRequest
from app.utils.dependencies import get_login_data, UnifiedLoginRequest
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
async def register(
    user_info: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user."""
    # Check if user already exists
    result = await db.execute(select(User).filter_by(email=user_info.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")
    
    # Create user
    user = User(
        email=user_info.email,
        hashed_password=get_password_hash(user_info.password),
        full_name=user_info.full_name,
        company_name=user_info.company_name,
        phone_number=user_info.phone_number,
        address=user_info.address
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create access and refresh tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Return user
    return UserResponse(
        id=user.id,
        email=user.email,
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post(
    "/login",
    response_model=Token,
    summary="User login",
    description="""
    Login endpoint that supports both JSON and form-encoded requests.
    
    **JSON Request** (Content-Type: application/json):
    ```json
    {
        "email": "user@example.com",
        "password": "yourpassword"
    }
    ```
    
    **Form-encoded Request** (Content-Type: application/x-www-form-urlencoded):
    - username: user@example.com (email address)
    - password: yourpassword
    """,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "format": "email"},
                            "password": {"type": "string", "format": "password"}
                        },
                        "required": ["email", "password"]
                    },
                    "example": {
                        "email": "user@example.com",
                        "password": "yourpassword"
                    }
                },
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "description": "Email address"},
                            "password": {"type": "string", "format": "password"}
                        },
                        "required": ["username", "password"]
                    }
                }
            }
        }
    }
)
async def login(
    login_data: UnifiedLoginRequest = Depends(get_login_data),
    db: AsyncSession = Depends(get_db)
):
    """Login and get access and refresh tokens.
    
    Supports both JSON (application/json) and form-encoded (application/x-www-form-urlencoded) requests.
    For form-encoded requests, use 'username' field (which should contain the email).
    For JSON requests, use 'email' and 'password' fields.
    """
    # Get user
    user = await db.execute(select(User).where(User.email == login_data.email))
    user = user.scalar_one_or_none()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access and refresh tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Return tokens
    return Token(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    payload = decoded_token(token_data.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Verify user still exists and is active
    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Return new access token
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )