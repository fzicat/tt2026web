from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from web.routers import ibkr, fbn

app = FastAPI(title="TradeTools Web")

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

# Routers
app.include_router(ibkr.router, prefix="/api/ibkr", tags=["ibkr"])
app.include_router(fbn.router, prefix="/api/fbn", tags=["fbn"])

@app.get("/")
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "templates", "index.html"))
