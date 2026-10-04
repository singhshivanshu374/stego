"""
SecureStego — Auth API Routes

POST /auth/register — Create user, generate RSA keypair, return private key once.
POST /auth/login    — Authenticate user, return JWT.

Security notes:
  - Client-side key generation is the more secure alternative to server-side
    generation. In that model, the client generates the RSA keypair locally,
    sends only the public key during registration, and manages the private key
    entirely on their device. This eliminates the need for the server to ever
    handle private keys. Server-side generation is used here for simplicity
    in a portfolio/demo context.
  - The private key is returned ONCE during registration and then stored
    encrypted at rest (Rule 5.5). The server cannot return it again in plaintext.
  - Passwords are hashed with bcrypt before storage (Rule 5.1).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import (
    create_access_token,
    encrypt_private_key,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.postgres import get_db
from app.models.db_models import User
from app.models.schemas import (
    UserLoginRequest,
    UserLoginResponse,
    UserRegisterRequest,
    UserRegisterResponse,
)
from app.services.crypto_service import generate_rsa_keypair

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account with an RSA keypair. "
                "Returns the private key ONCE — save it securely.",
)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user.

    1. Check username uniqueness.
    2. Hash password with bcrypt.
    3. Generate RSA keypair server-side.
    4. Encrypt private key at rest with server master key (Rule 5.5).
    5. Store user + public key + encrypted private key in Postgres.
    6. Return private key (plaintext PEM) to the client ONCE.
    """
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered.",
        )

    # Hash password
    password_hash = hash_password(request.password)

    # Generate RSA keypair
    public_pem, private_pem = generate_rsa_keypair()

    # Encrypt private key for at-rest storage (Rule 5.5)
    encrypted_private = encrypt_private_key(private_pem)

    # Create user record
    user = User(
        username=request.username,
        password_hash=password_hash,
        public_key_pem=public_pem.decode("utf-8"),
        encrypted_private_key=encrypted_private,
    )
    db.add(user)
    await db.flush()  # Get the generated ID
    await db.refresh(user)

    return UserRegisterResponse(
        id=user.id,
        username=user.username,
        private_key_pem=private_pem.decode("utf-8"),
    )


@router.post(
    "/login",
    response_model=UserLoginResponse,
    summary="Login and get JWT",
    description="Authenticate with username/password and receive a JWT access token.",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return JWT.

    Returns a generic error for invalid credentials — doesn't reveal whether
    the username exists or the password was wrong (defense against enumeration).
    """
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token = create_access_token(data={"sub": user.username, "user_id": user.id})

    return UserLoginResponse(access_token=token)


@router.get(
    "/users",
    response_model=list[str],
    summary="Search usernames",
    description="Search for registered usernames (used for recipient selection).",
)
async def search_users(
    q: str = Query("", min_length=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search usernames by prefix."""
    if not q:
        # Return all users (limit to 50 for safety)
        stmt = select(User.username).limit(50)
    else:
        stmt = select(User.username).where(User.username.ilike(f"{q}%")).limit(10)
        
    result = await db.execute(stmt)
    return result.scalars().all()
