import os

from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

# Load env vars
load_dotenv()

app = FastAPI()

# Add session middleware (required for OAuth)
app.add_middleware(SessionMiddleware, secret_key="SUPER_SECRET_KEY")

# Configure OAuth
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@app.get("/")
async def homepage(request: Request):
    user = request.session.get("user")
    if user:
        return HTMLResponse(
            f"<h1>Welcome {user['name']}</h1><p>Email: {user['email']}</p>"
            '<a href="/logout">Logout</a>'
        )
    return HTMLResponse('<a href="/login">Sign in with Google</a>')


@app.get("/login/google")
async def login(request: Request):
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token["userinfo"]
    request.session["user"] = dict(user_info)  # Save user in session
    return RedirectResponse(url="/")


@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/")
