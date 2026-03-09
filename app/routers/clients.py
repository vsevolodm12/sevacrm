from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.models import Client, Partner, Payment, User

router = APIRouter(prefix="/clients")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def clients_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clients = db.query(Client).order_by(Client.name).all()
    partners = db.query(Partner).filter(Partner.is_active == True).all()
    today = date.today()

    clients_with_payment = []
    for client in clients:
        payment = (
            db.query(Payment)
            .filter(
                Payment.client_id == client.id,
                Payment.month == today.month,
                Payment.year == today.year,
            )
            .first()
        )
        clients_with_payment.append({
            "client": client,
            "current_payment": payment,
        })

    return templates.TemplateResponse(
        "clients/index.html",
        {
            "request": request,
            "current_user": current_user,
            "clients_with_payment": clients_with_payment,
            "partners": partners,
            "today": today,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_client(
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    company: str = Form(""),
    monthly_fee: float = Form(0),
    currency: str = Form("RUB"),
    partner_id: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = Client(
        name=name,
        phone=phone or None,
        email=email or None,
        company=company or None,
        monthly_fee=monthly_fee,
        currency=currency,
        partner_id=int(partner_id) if partner_id else None,
        notes=notes or None,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    today = date.today()
    response = templates.TemplateResponse(
        "clients/card.html",
        {
            "request": request,
            "client": client,
            "current_payment": None,
            "today": today,
        },
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Клиент добавлен", "type": "success"}}'
    return response


@router.get("/{client_id}", response_class=HTMLResponse)
async def client_detail(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return HTMLResponse("Клиент не найден", status_code=404)

    payments = (
        db.query(Payment)
        .filter(Payment.client_id == client_id)
        .order_by(Payment.year.desc(), Payment.month.desc())
        .all()
    )
    partners = db.query(Partner).filter(Partner.is_active == True).all()
    today = date.today()

    return templates.TemplateResponse(
        "clients/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "client": client,
            "payments": payments,
            "partners": partners,
            "today": today,
        },
    )


@router.get("/{client_id}/edit", response_class=HTMLResponse)
async def edit_client_form(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return HTMLResponse("Клиент не найден", status_code=404)
    partners = db.query(Partner).filter(Partner.is_active == True).all()
    return templates.TemplateResponse(
        "clients/form.html",
        {"request": request, "client": client, "partners": partners},
    )


@router.put("/{client_id}", response_class=HTMLResponse)
async def update_client(
    client_id: int,
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    company: str = Form(""),
    monthly_fee: float = Form(0),
    currency: str = Form("RUB"),
    partner_id: str = Form(""),
    is_active: str = Form("on"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return HTMLResponse("Клиент не найден", status_code=404)

    client.name = name
    client.phone = phone or None
    client.email = email or None
    client.company = company or None
    client.monthly_fee = monthly_fee
    client.currency = currency
    client.partner_id = int(partner_id) if partner_id else None
    client.is_active = is_active == "on"
    client.notes = notes or None
    db.commit()
    db.refresh(client)

    today = date.today()
    current_payment = (
        db.query(Payment)
        .filter(
            Payment.client_id == client.id,
            Payment.month == today.month,
            Payment.year == today.year,
        )
        .first()
    )

    response = templates.TemplateResponse(
        "clients/card.html",
        {
            "request": request,
            "client": client,
            "current_payment": current_payment,
            "today": today,
        },
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Клиент обновлён", "type": "success"}}'
    return response


@router.delete("/{client_id}")
async def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        db.delete(client)
        db.commit()
    response = Response(content="", status_code=200)
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Клиент удалён", "type": "success"}}'
    return response


@router.post("/{client_id}/payments", response_class=HTMLResponse)
async def create_payment(
    client_id: int,
    request: Request,
    month: int = Form(...),
    year: int = Form(...),
    amount: float = Form(...),
    currency: str = Form("RUB"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return HTMLResponse("Клиент не найден", status_code=404)

    # Check if payment already exists for this month
    existing = (
        db.query(Payment)
        .filter(
            Payment.client_id == client_id,
            Payment.month == month,
            Payment.year == year,
        )
        .first()
    )
    if existing:
        existing.amount = amount
        existing.currency = currency
        existing.notes = notes or None
        db.commit()
        db.refresh(existing)
        payment = existing
    else:
        payment = Payment(
            client_id=client_id,
            month=month,
            year=year,
            amount=amount,
            currency=currency,
            notes=notes or None,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

    response = templates.TemplateResponse(
        "clients/payment_row.html",
        {"request": request, "payment": payment},
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Платёж сохранён", "type": "success"}}'
    return response


@router.put("/payments/{payment_id}/toggle", response_class=HTMLResponse)
async def toggle_payment(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return HTMLResponse("Платёж не найден", status_code=404)

    payment.is_paid = not payment.is_paid
    payment.paid_at = datetime.utcnow() if payment.is_paid else None
    db.commit()
    db.refresh(payment)

    # Return updated status badge
    today = date.today()
    response = templates.TemplateResponse(
        "clients/payment_toggle.html",
        {"request": request, "payment": payment, "today": today},
    )
    return response
