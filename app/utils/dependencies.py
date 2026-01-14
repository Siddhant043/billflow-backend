from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.security import decoded_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decoded_token(token)
        if payload is None:
            raise credentials_exception
        user_id: str = payload.get("sub")
        # token_type: str = payload.get("type")
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

        if user is None:
            raise credentials_exception
        
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")

        return user

    except Exception as e:
        raise credentials_exception

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


class UnifiedLoginRequest:
    """Unified login request that handles both JSON and form-encoded data."""
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password


async def get_login_data(
    request: Request
) -> UnifiedLoginRequest:
    """
    Dependency that handles both JSON and form-encoded login requests.
    Checks content-type header to determine which format to parse.
    """
    content_type = request.headers.get("content-type", "").lower()
    
    # If JSON content type, parse as JSON
    if "application/json" in content_type:
        try:
            body = await request.json()
            email = body.get("email")
            password = body.get("password")
            if not email or not password:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Missing 'email' or 'password' in request body"
                )
            return UnifiedLoginRequest(email=email, password=password)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid JSON format: {str(e)}"
            )
    
    # Otherwise, parse as form-encoded data (OAuth2PasswordRequestForm style)
    # This handles Swagger UI which sends form-encoded data
    try:
        form_data = await request.form()
        username = form_data.get("username") or form_data.get("email")
        password = form_data.get("password")
        
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing 'username' (or 'email') or 'password' in form data"
            )
        
        return UnifiedLoginRequest(email=username, password=password)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid form data: {str(e)}"
        )

