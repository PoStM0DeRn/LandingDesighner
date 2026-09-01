import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import (
    authenticate,
    create_session,
    get_user_created,
    register,
    require_user,
    revoke_token,
    _token_from_request,
)
from app.models.schemas import AuthRequest, AuthResponse, UserPublic

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register_endpoint(body: AuthRequest):
    try:
        user = register(body.nickname, body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    token = create_session(user["nickname"])
    return AuthResponse(token=token, user=UserPublic(**user))


@router.post("/login", response_model=AuthResponse)
def login_endpoint(body: AuthRequest):
    time.sleep(0.5)  # brute-force damping
    nickname = authenticate(body.nickname, body.password)
    if not nickname:
        raise HTTPException(status_code=401, detail="Неверный никнейм или пароль")
    token = create_session(nickname)
    return AuthResponse(token=token, user=UserPublic(nickname=nickname, created_at=get_user_created(nickname)))


@router.post("/logout", status_code=204)
def logout_endpoint(request: Request):
    token = _token_from_request(request)
    if token:
        revoke_token(token)


@router.get("/me", response_model=UserPublic)
def me_endpoint(user: str = Depends(require_user)):
    return UserPublic(nickname=user, created_at=get_user_created(user))
