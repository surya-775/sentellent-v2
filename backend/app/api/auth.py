from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.core.deps import get_current_user
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = settings.OAUTH_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await oauth.google.parse_id_token(request, token)

    google_sub = userinfo["sub"]
    email = userinfo["email"]
    name = userinfo.get("name")
    picture = userinfo.get("picture")

    user = db.query(User).filter(User.google_sub == google_sub).first()
    if not user:
        user = User(google_sub=google_sub, email=email, name=name, picture_url=picture)
        db.add(user)
        db.commit()
        db.refresh(user)

    jwt_token = create_access_token(user.id, user.email)
    # Redirect back to frontend with token — frontend stores it and calls the API with Authorization: Bearer
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}")


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "picture_url": user.picture_url}
