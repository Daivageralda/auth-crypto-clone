from fastapi import APIRouter, Request, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.controllers import auth_controller
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def show_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def process_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    result = await auth_controller.login_user(email, password)
    if "error" in result:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Login gagal. Periksa email dan password."
        })
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie("token", result["access_token"])  
    return response

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
