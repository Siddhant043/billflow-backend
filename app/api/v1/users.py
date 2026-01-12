from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db

from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, UserUpdatePassword
from app.utils.dependencies import get_current_active_user
from app.core.security import get_password_hash, verify_password
from app.core.redis import redis_client

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user information."""
    # Update fields
    update_data = user_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    # Invalidate cache
    await redis_client.delete(f"user:{current_user.id}")
    
    return current_user

@router.put("/me/password")
async def update_password(
    password_update: UserUpdatePassword,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user password."""
    # Verify current password
    if not verify_password(password_update.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(password_update.new_password)
    
    await db.commit()
    
    return {"message": "Password updated successfully"}

@router.delete("/me")
async def delete_current_user(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete current user account."""
    await db.delete(current_user)
    await db.commit()
    
    # Clear cache
    await redis_client.delete(f"user:{current_user.id}")
    
    return {"message": "Account deleted successfully"}