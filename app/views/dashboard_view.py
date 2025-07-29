from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
from app.controllers import auth_controller
from app.ws.exchange_manager import (
    build_market_payload
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent  
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates") 

templates = Jinja2Templates(directory=TEMPLATE_DIR)

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    data = await build_market_payload()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "markets": data
    })
