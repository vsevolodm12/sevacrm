import os
import re
from datetime import datetime, date
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models.models import Client, Document, Partner, Payment, User

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}


def _secure_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = re.sub(r"[^\w\s\-.]", "_", filename)
    return re.sub(r"\s+", "_", filename) or "file"


def _parse_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


async def _save_document(db, file: UploadFile, title: str, doc_type: str, client_id: int):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return
    content = await file.read()
    if not content:
        return
    now = datetime.utcnow()
    safe_name = _secure_filename(file.filename or "file")
    stored = f"{int(now.timestamp())}_{safe_name}"
    rel_dir = os.path.join(settings.upload_dir, str(now.year), str(now.month).zfill(2))
    os.makedirs(rel_dir, exist_ok=True)
    file_path = os.path.join(rel_dir, stored)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    doc = Document(
        title=title or safe_name,
        client_id=client_id,
        doc_type=doc_type,
        file_path=file_path,
        file_name=file.filename or safe_name,
        file_size=len(content),
    )
    db.add(doc)
    db.commit()

router = APIRouter(prefix="/orders")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def orders_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders = db.query(Client).order_by(Client.name).all()
    partners = db.query(Partner).filter(Partner.is_active == True).all()
    today = date.today()

    orders_with_payment = []
    for order in orders:
        payment = (
            db.query(Payment)
            .filter(
                Payment.client_id == order.id,
                Payment.month == today.month,
                Payment.year == today.year,
            )
            .first()
        )
        orders_with_payment.append({
            "order": order,
            "current_payment": payment,
        })

    return templates.TemplateResponse(
        "orders/index.html",
        {
            "request": request,
            "current_user": current_user,
            "orders_with_payment": orders_with_payment,
            "partners": partners,
            "today": today,
        },
    )


@router.get("/{order_id}/edit", response_class=HTMLResponse)
async def edit_order_form(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Client).filter(Client.id == order_id).first()
    if not order:
        return HTMLResponse("Заказ не найден", status_code=404)
    partners = db.query(Partner).filter(Partner.is_active == True).all()
    return templates.TemplateResponse(
        "orders/form.html",
        {"request": request, "order": order, "partners": partners},
    )


@router.get("/{order_id}", response_class=HTMLResponse)
async def order_detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.models import Document
    order = db.query(Client).filter(Client.id == order_id).first()
    if not order:
        return HTMLResponse("Заказ не найден", status_code=404)
    partners = db.query(Partner).filter(Partner.is_active == True).all()
    payments = (
        db.query(Payment)
        .filter(Payment.client_id == order_id)
        .order_by(Payment.year.desc(), Payment.month.desc())
        .all()
    )
    documents = (
        db.query(Document)
        .filter(Document.client_id == order_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    today = date.today()
    return templates.TemplateResponse(
        "orders/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "order": order,
            "partners": partners,
            "payments": payments,
            "documents": documents,
            "today": today,
        }
    )


@router.post("", response_class=HTMLResponse)
async def create_order(
    request: Request,
    title: str = Form(""),
    name: str = Form(""),
    phone: str = Form(""),
    monthly_fee: float = Form(0),
    dev_price: float = Form(0),
    advance_amount: float = Form(0),
    currency: str = Form("RUB"),
    partner_id: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    doc_files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = Client(
        title=title or None,
        name=name or title or "Без названия",
        phone=phone or None,
        monthly_fee=monthly_fee,
        dev_price=dev_price,
        advance_amount=advance_amount,
        currency=currency,
        partner_id=int(partner_id) if partner_id else None,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    for doc_file in (doc_files or []):
        if doc_file and doc_file.filename:
            title = os.path.splitext(doc_file.filename)[0]
            await _save_document(db, doc_file, title, "other", order.id)

    today = date.today()
    response = templates.TemplateResponse(
        "orders/card.html",
        {
            "request": request,
            "order": order,
            "current_payment": None,
            "today": today,
        },
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Заказ добавлен", "type": "success"}}'
    return response


@router.put("/{order_id}", response_class=HTMLResponse)
async def update_order(
    order_id: int,
    request: Request,
    title: str = Form(""),
    name: str = Form(...),
    phone: str = Form(""),
    monthly_fee: float = Form(0),
    dev_price: float = Form(0),
    advance_amount: float = Form(0),
    currency: str = Form("RUB"),
    partner_id: str = Form(""),
    is_active: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Client).filter(Client.id == order_id).first()
    if not order:
        return HTMLResponse("Заказ не найден", status_code=404)

    order.title = title or None
    order.name = name
    order.phone = phone or None
    order.monthly_fee = monthly_fee
    order.dev_price = dev_price
    order.advance_amount = advance_amount
    order.currency = currency
    order.partner_id = int(partner_id) if partner_id else None
    order.is_active = is_active == "on"
    order.start_date = _parse_date(start_date)
    order.end_date = _parse_date(end_date)
    db.commit()
    db.refresh(order)

    today = date.today()
    current_payment = (
        db.query(Payment)
        .filter(
            Payment.client_id == order.id,
            Payment.month == today.month,
            Payment.year == today.year,
        )
        .first()
    )

    response = templates.TemplateResponse(
        "orders/card.html",
        {
            "request": request,
            "order": order,
            "current_payment": current_payment,
            "today": today,
        },
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Заказ обновлён", "type": "success"}}'
    return response


@router.delete("/{order_id}")
async def delete_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Client).filter(Client.id == order_id).first()
    if order:
        db.delete(order)
        db.commit()
    response = Response(content="", status_code=200)
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Заказ удалён", "type": "success"}}'
    # If deleted from detail page, tell HTMX to navigate back to list
    current_url = request.headers.get("HX-Current-URL", "")
    if f"/orders/{order_id}" in current_url:
        response.headers["HX-Location"] = '{"path":"/orders","target":"#page-content","select":"#page-content","swap":"outerHTML"}'
    return response


@router.post("/{order_id}/payments", response_class=HTMLResponse)
async def create_payment(
    order_id: int,
    request: Request,
    month: int = Form(...),
    year: int = Form(...),
    amount: float = Form(...),
    currency: str = Form("RUB"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Client).filter(Client.id == order_id).first()
    if not order:
        return HTMLResponse("Заказ не найден", status_code=404)

    existing = (
        db.query(Payment)
        .filter(
            Payment.client_id == order_id,
            Payment.month == month,
            Payment.year == year,
        )
        .first()
    )
    if existing:
        existing.amount = amount
        existing.currency = currency
        db.commit()
        db.refresh(existing)
        payment = existing
    else:
        payment = Payment(
            client_id=order_id,
            month=month,
            year=year,
            amount=amount,
            currency=currency,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

    response = templates.TemplateResponse(
        "orders/payment_row.html",
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

    today = date.today()
    response = templates.TemplateResponse(
        "orders/payment_toggle.html",
        {"request": request, "payment": payment, "today": today},
    )
    return response


@router.delete("/payments/{payment_id}")
async def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment:
        db.delete(payment)
        db.commit()
    response = Response(content="", status_code=200)
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Платёж удалён", "type": "success"}}'
    return response
