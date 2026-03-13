from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from app.templates_config import templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.models import Client, Payment, User
from app.services.currency import currency_service
from app.services.stats import stats_service

router = APIRouter()


@router.get("/api/rates", response_class=JSONResponse)
async def get_rates(current_user: User = Depends(get_current_user)):
    usd = await currency_service.get_rate("USD", "RUB")
    eur = await currency_service.get_rate("EUR", "RUB")
    return {"RUB": 1.0, "USD": round(usd, 2), "EUR": round(eur, 2)}


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    month: int = None,
    year: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    if not month:
        month = today.month
    if not year:
        year = today.year
    month = max(1, min(12, month))

    stats = await stats_service.get_dashboard_stats(db, month, year)

    # Active clients with payment status for current month (maintenance payments only)
    active_clients = db.query(Client).filter(Client.maintenance_enabled == True).all()
    clients_with_status = []
    for client in active_clients:
        payment = (
            db.query(Payment)
            .filter(
                Payment.client_id == client.id,
                Payment.month == month,
                Payment.year == year,
                Payment.payment_type == "maintenance",
            )
            .order_by(Payment.id.desc())
            .first()
        )
        clients_with_status.append({
            "client": client,
            "payment": payment,
        })

    active_projects = []

    month_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "stats": stats,
            "clients_with_status": clients_with_status,
            "active_projects": active_projects,
            "month": month,
            "year": year,
            "month_name": month_names[month - 1],
            "month_names": month_names,
        },
    )


@router.get("/dashboard/stats", response_class=HTMLResponse)
async def dashboard_stats(
    request: Request,
    month: int = None,
    year: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    if not month:
        month = today.month
    if not year:
        year = today.year

    # Clamp month
    month = max(1, min(12, month))

    stats = await stats_service.get_dashboard_stats(db, month, year)

    active_clients = db.query(Client).filter(Client.maintenance_enabled == True).all()
    clients_with_status = []
    for client in active_clients:
        payment = (
            db.query(Payment)
            .filter(
                Payment.client_id == client.id,
                Payment.month == month,
                Payment.year == year,
                Payment.payment_type == "maintenance",
            )
            .order_by(Payment.id.desc())
            .first()
        )
        clients_with_status.append({
            "client": client,
            "payment": payment,
        })

    active_projects = []

    month_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]

    return templates.TemplateResponse(
        "partials/dashboard_content.html",
        {
            "request": request,
            "current_user": current_user,
            "stats": stats,
            "clients_with_status": clients_with_status,
            "active_projects": active_projects,
            "month": month,
            "year": year,
            "month_name": month_names[month - 1],
            "month_names": month_names,
        },
    )
