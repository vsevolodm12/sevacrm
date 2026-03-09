import os

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import Base, engine
from app.routers import auth, dashboard, partners, orders, projects, documents, stats

app = FastAPI(title="SevaCRM", version="1.0.0")

# Create upload directory
os.makedirs(settings.upload_dir, exist_ok=True)

# Mount uploads as static files
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# Include routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(partners.router)
app.include_router(orders.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(stats.router)

templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303:
        return RedirectResponse(url=exc.headers.get("Location", "/login"), status_code=303)
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
    )
