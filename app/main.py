import os

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.templates_config import templates
from app.database import Base, engine
from app.routers import auth, dashboard, partners, clients, orders, documents, stats

app = FastAPI(title="SevaCRM", version="1.0.0")

# Create upload directory
os.makedirs(settings.upload_dir, exist_ok=True)

# Mount static assets
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount uploads as static files
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# Include routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(partners.router)
app.include_router(clients.router)
app.include_router(orders.router)

app.include_router(documents.router)
app.include_router(stats.router)

def ensure_sqlite_schema():
    if engine.url.get_backend_name() != "sqlite":
        return

    with engine.begin() as conn:
        client_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(clients)").fetchall()
        }
        missing_client_columns = {
            "email": "ALTER TABLE clients ADD COLUMN email VARCHAR(255)",
            "company": "ALTER TABLE clients ADD COLUMN company VARCHAR(255)",
            "notes": "ALTER TABLE clients ADD COLUMN notes TEXT",
            "is_completed": "ALTER TABLE clients ADD COLUMN is_completed BOOLEAN DEFAULT 0",
            "completed_at": "ALTER TABLE clients ADD COLUMN completed_at DATETIME",
        }
        for column, statement in missing_client_columns.items():
            if column not in client_columns:
                conn.exec_driver_sql(statement)

        payment_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(payments)").fetchall()
        }
        missing_payment_columns = {
            "payment_day": "ALTER TABLE payments ADD COLUMN payment_day INTEGER DEFAULT 1",
            "payment_type": "ALTER TABLE payments ADD COLUMN payment_type VARCHAR(20) DEFAULT 'order'",
            "amount_rub": "ALTER TABLE payments ADD COLUMN amount_rub NUMERIC(14,2)",
        }
        for column, statement in missing_payment_columns.items():
            if column not in payment_columns:
                conn.exec_driver_sql(statement)


@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()


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
