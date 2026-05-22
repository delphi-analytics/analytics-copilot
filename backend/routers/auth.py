from datetime import datetime, timedelta
from typing import Annotated, List
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from backend.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from backend.auth.dependencies import get_current_user, get_current_user_optional
from backend.database import get_db
from backend.models.user import User
from backend.config import settings
import secrets

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    preferences: dict | None = None


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    response: Response = None
):
    """Authenticate user and return JWT tokens."""
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    # Verify password
    if not user or not user.verify_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Update last login
    await db.execute(
        update(User).where(User.id == user.id).values(last_login=datetime.utcnow())
    )
    await db.commit()

    # Create tokens
    token_data = {"sub": user.id, "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Set refresh token as httpOnly cookie
    if response:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,  # Set True in production with HTTPS
            samesite="lax",
            max_age=60 * 60 * 24 * 7  # 7 days
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "is_active": user.is_active,
            "preferences": user.preferences
        }
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str | None = None,
    refresh_token_cookie: str | None = Cookie(None),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    response: Response = None
):
    """Refresh access token using refresh token."""
    token = refresh_token or refresh_token_cookie

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    # Verify refresh token
    payload = verify_token(token, "refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Get user
    user_id = payload.get("sub")
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Create new tokens
    token_data = {"sub": user.id, "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    # Update cookie
    if response:
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=60 * 60 * 24 * 7
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "is_active": user.is_active,
            "preferences": user.preferences
        }
    )


@router.post("/logout")
async def logout(response: Response):
    """Logout user by clearing refresh token cookie."""
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user_optional)]
):
    """Get current user info. Returns null if not authenticated."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        is_active=current_user.is_active,
        preferences=current_user.preferences
    )


# Demo user creation DISABLED - only admin can create users through /users endpoint
@router.post("/demo/create-user", include_in_schema=False)
async def create_demo_user_disabled(
    email: EmailStr,
    password: str,
    name: str = "Demo User",
    role: str = "business_analyst",
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Demo user creation is disabled. Admins should use the /users endpoint instead."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Demo user creation is disabled. Please use the Admin Panel > Users to create new user accounts."
    )

    # Check if user exists
    result = await db.execute(
        select(User).where(User.email == email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )

    # Create user
    user = User(
        email=email,
        name=name,
        hashed_password=User.hash_password(password),
        role=role,
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role
    }


# Admin user management endpoints
class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str
    role: str = "business_analyst"  # business_analyst | non_tech_user | team_member | admin


class UpdateUserRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """List all users. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list users"
        )

    result = await db.execute(select(User))
    users = result.scalars().all()

    return [
        UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            preferences=user.preferences
        )
        for user in users
    ]


@router.post("/users")
async def create_user(
    request: CreateUserRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Create a new user. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create users"
        )

    # Check if user exists
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Generate a random password
    temp_password = secrets.token_urlsafe(12)

    # Create user
    user = User(
        email=request.email,
        name=request.name,
        hashed_password=User.hash_password(temp_password),
        role=request.role,
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "temp_password": temp_password,  # Return temp password for admin to share
        "message": f"User created successfully. Temporary password: {temp_password}"
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Update a user. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update users"
        )

    # Don't allow self-update
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update your own account through this endpoint"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update fields
    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.role is not None:
        update_data["role"] = request.role
    if request.is_active is not None:
        update_data["is_active"] = request.is_active

    await db.execute(
        update(User).where(User.id == user_id).values(**update_data)
    )
    await db.commit()

    return {"message": "User updated successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Delete a user. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete users"
        )

    # Don't allow self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    await db.execute(select(User).where(User.id == user_id))
    # Actually delete using the session
    import sqlalchemy as sa
    await db.execute(sa.delete(User).where(User.id == user_id))
    await db.commit()

    return {"message": "User deleted successfully"}


@router.post("/reset-password")
async def reset_user_password(
    email: EmailStr,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Reset a user's password. Admin only (or user for their own account)."""
    # Only admins can reset other users' passwords
    # Users can reset their own password if they verify their email
    if current_user.role != "admin" and current_user.email != email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reset other users' passwords"
        )

    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Generate new temporary password
    temp_password = secrets.token_urlsafe(12)

    await db.execute(
        update(User).where(User.id == user.id).values(
            hashed_password=User.hash_password(temp_password)
        )
    )
    await db.commit()

    return {
        "message": "Password reset successfully",
        "temp_password": temp_password,
        "email": email
    }


# ─── Profile & Preferences (own-account) endpoints ────────────────────────────

class UpdateProfileRequest(BaseModel):
    name: str | None = None
    email: EmailStr | None = None


class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdatePreferencesRequest(BaseModel):
    preferences: dict


@router.put("/me")
async def update_own_profile(
    request: UpdateProfileRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Update own profile (name, email)."""
    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.email is not None:
        result = await db.execute(select(User).where(User.email == request.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
        update_data["email"] = request.email

    await db.execute(update(User).where(User.id == current_user.id).values(**update_data))
    await db.commit()

    return {"message": "Profile updated"}


@router.put("/me/password")
async def update_own_password(
    request: UpdatePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Change own password."""
    if not current_user.verify_password(request.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    await db.execute(
        update(User).where(User.id == current_user.id).values(
            hashed_password=User.hash_password(request.new_password)
        )
    )
    await db.commit()
    return {"message": "Password updated"}


@router.get("/me/preferences")
async def get_own_preferences(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Get own preferences."""
    return {"preferences": current_user.preferences or {}}


@router.put("/me/preferences")
async def update_own_preferences(
    request: UpdatePreferencesRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Update own preferences (theme, chart defaults, AI settings, etc)."""
    await db.execute(
        update(User).where(User.id == current_user.id).values(
            preferences=request.preferences
        )
    )
    await db.commit()
    return {"message": "Preferences updated"}
