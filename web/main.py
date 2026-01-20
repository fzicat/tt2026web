from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

from shared.config import SUPABASE_URL, SUPABASE_ANON_KEY
from shared.supabase_client import verify_token
from web.routers import ibkr, fbn

app = FastAPI(title="TradeTools Web")

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)

# Templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")


# Auth dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the JWT token and return user info."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    user_info = verify_token(token)

    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_info


# Include routers with auth dependency
app.include_router(
    ibkr.router,
    prefix="/api/ibkr",
    tags=["ibkr"],
    dependencies=[Depends(get_current_user)]
)
app.include_router(
    fbn.router,
    prefix="/api/fbn",
    tags=["fbn"],
    dependencies=[Depends(get_current_user)]
)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main HTML page with Supabase config."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "supabase_url": SUPABASE_URL,
            "supabase_anon_key": SUPABASE_ANON_KEY,
        }
    )
