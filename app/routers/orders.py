import os
import re
from datetime import datetime, date
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from app.templates_config import templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.htmx import set_htmx_toast
from app.models.models import Client, Document, Partner, Payment, User
from app.services.currency import currency_service

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


@router.get("", response_class=HTMLResponse)
async def orders_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders = sorted(
        db.query(Client).order_by(Client.name).all(),
        key=lambda o: (1 if o.is_completed else 0)
    )
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
                Payment.payment_type == "maintenance",
            )
            .first()
        )
        orders_with_payment.append({
            "order": order,
            "current_payment": payment,
        })

    # Моя доля обслуживания в RUB (только с включённым обслуживанием, 50/50 с партнёром)
    maintenance_rub = 0.0
    for item in orders_with_payment:
        o = item["order"]
        if o.maintenance_enabled:
            fee_rub = await currency_service.convert_to_rub(float(o.monthly_fee or 0), o.currency or "RUB")
            maintenance_rub += fee_rub / 2 if o.partner_id else fee_rub

    return templates.TemplateResponse(
        "orders/index.html",
        {
            "request": request,
            "current_user": current_user,
            "orders_with_payment": orders_with_payment,
            "maintenance_rub": maintenance_rub,
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
    current_url = (request.headers.get("HX-Current-URL") or "").rstrip("/")
    detail_mode = current_url.endswith(f"/orders/{order_id}")
    return templates.TemplateResponse(
        "orders/form.html",
        {"request": request, "order": order, "partners": partners, "detail_mode": detail_mode},
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
    all_payments = (
        db.query(Payment)
        .filter(Payment.client_id == order_id)
        .order_by(Payment.year.desc(), Payment.month.desc(), Payment.id.desc())
        .all()
    )
    payments = [p for p in all_payments if p.payment_type != "maintenance"]
    maintenance_payments = [p for p in all_payments if p.payment_type == "maintenance"]
    all_docs = (
        db.query(Document)
        .filter(Document.client_id == order_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    documents = [d for d in all_docs if d.doc_type not in ("act", "invoice")]
    maintenance_acts = [d for d in all_docs if d.doc_type == "act"]
    maintenance_invoices = [d for d in all_docs if d.doc_type == "invoice"]
    today = date.today()
    paid_total = sum(float(p.amount) for p in payments if p.is_paid)
    return templates.TemplateResponse(
        "orders/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "order": order,
            "partners": partners,
            "payments": payments,
            "maintenance_payments": maintenance_payments,
            "documents": documents,
            "maintenance_acts": maintenance_acts,
            "maintenance_invoices": maintenance_invoices,
            "today": today,
            "paid_total": paid_total,
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
    return set_htmx_toast(response, "Заказ добавлен")


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
    is_completed: str = Form(""),
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
    new_completed = is_completed == "on"
    if new_completed and not order.is_completed:
        order.completed_at = datetime.utcnow()
    elif not new_completed:
        order.completed_at = None
    order.is_completed = new_completed
    order.start_date = _parse_date(start_date)
    order.end_date = _parse_date(end_date)
    db.commit()
    db.refresh(order)

    current_url = (request.headers.get("HX-Current-URL") or "").rstrip("/")
    detail_mode = current_url.endswith(f"/orders/{order_id}")
    partners = db.query(Partner).filter(Partner.is_active == True).all()
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

    if detail_mode:
        all_payments = (
            db.query(Payment)
            .filter(Payment.client_id == order_id)
            .order_by(Payment.year.desc(), Payment.month.desc(), Payment.id.desc())
            .all()
        )
        payments = [p for p in all_payments if p.payment_type != "maintenance"]
        maintenance_payments = [p for p in all_payments if p.payment_type == "maintenance"]
        all_docs = (
            db.query(Document)
            .filter(Document.client_id == order_id)
            .order_by(Document.created_at.desc())
            .all()
        )
        documents = [d for d in all_docs if d.doc_type not in ("act", "invoice")]
        maintenance_acts = [d for d in all_docs if d.doc_type == "act"]
        maintenance_invoices = [d for d in all_docs if d.doc_type == "invoice"]
        paid_total = sum(float(p.amount) for p in payments if p.is_paid)
        response = templates.TemplateResponse(
            "orders/detail.html",
            {
                "request": request,
                "current_user": current_user,
                "order": order,
                "partners": partners,
                "payments": payments,
                "maintenance_payments": maintenance_payments,
                "documents": documents,
                "maintenance_acts": maintenance_acts,
                "maintenance_invoices": maintenance_invoices,
                "today": today,
                "paid_total": paid_total,
            },
        )
    else:
        response = templates.TemplateResponse(
            "orders/card.html",
            {
                "request": request,
                "order": order,
                "current_payment": current_payment,
                "today": today,
            },
        )
    return set_htmx_toast(response, "Заказ обновлён")


@router.patch("/{order_id}/toggle-complete", response_class=HTMLResponse)
async def toggle_order_complete(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Client).filter(Client.id == order_id).first()
    if not order:
        return HTMLResponse("Заказ не найден", status_code=404)

    if order.is_completed:
        order.is_completed = False
        order.completed_at = None
    else:
        order.is_completed = True
        order.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    today = date.today()
    current_payment = (
        db.query(Payment)
        .filter(
            Payment.client_id == order.id,
            Payment.month == today.month,
            Payment.year == today.year,
            Payment.payment_type == "maintenance",
        )
        .first()
    )
    return templates.TemplateResponse(
        "orders/card.html",
        {"request": request, "order": order, "current_payment": current_payment, "today": today},
    )


@router.put("/{order_id}/status", response_class=HTMLResponse)
async def update_order_status(
    order_id: int,
    request: Request,
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Client).filter(Client.id == order_id).first()
    if not order:
        return HTMLResponse("Заказ не найден", status_code=404)
    if status == "active":
        order.is_active = True
        order.is_completed = False
        order.completed_at = None
    elif status == "completed":
        order.is_completed = True
        if not order.completed_at:
            order.completed_at = datetime.utcnow()
    elif status == "inactive":
        order.is_active = False
        order.is_completed = False
        order.completed_at = None
    db.commit()
    db.refresh(order)
    response = templates.TemplateResponse(
        "orders/status_badge.html",
        {"request": request, "order": order},
    )
    return set_htmx_toast(response, "Статус обновлён")


@router.put("/{order_id}/toggle-maintenance", response_class=HTMLResponse)
async def toggle_maintenance(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Client).filter(Client.id == order_id).first()
    if not order:
        return HTMLResponse("Заказ не найден", status_code=404)
    order.maintenance_enabled = not order.maintenance_enabled
    db.commit()
    db.refresh(order)
    response = templates.TemplateResponse(
        "orders/maintenance_status.html",
        {"request": request, "order": order},
    )
    return set_htmx_toast(response, "Обслуживание обновлено")


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
    # If deleted from detail page, tell HTMX to navigate back to list
    current_url = request.headers.get("HX-Current-URL", "")
    if f"/orders/{order_id}" in current_url:
        response.headers["HX-Location"] = '{"path":"/orders","target":"#page-content","select":"#page-content","swap":"outerHTML"}'
    return set_htmx_toast(response, "Заказ удалён")


@router.post("/{order_id}/payments", response_class=HTMLResponse)
async def create_payment(
    order_id: int,
    request: Request,
    payment_date: str = Form(""),
    amount: float = Form(...),
    currency: str = Form("RUB"),
    notes: str = Form(""),
    payment_type: str = Form("order"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Client).filter(Client.id == order_id).first()
    if not order:
        return HTMLResponse("Заказ не найден", status_code=404)
    parsed = _parse_date(payment_date)
    if parsed:
        month, year, day = parsed.month, parsed.year, parsed.day
    else:
        from datetime import date as _date
        today = _date.today()
        month, year, day = today.month, today.year, today.day

    amount_rub = await currency_service.convert_to_rub(amount, currency)
    payment = Payment(
        client_id=order_id,
        month=month,
        year=year,
        payment_day=day,
        payment_type=payment_type if payment_type in ("order", "maintenance") else "order",
        amount=amount,
        currency=currency,
        amount_rub=round(amount_rub, 2),
        notes=notes or None,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    tbody_id = "maintenance-payments-tbody" if payment.payment_type == "maintenance" else "payments-tbody"
    response = templates.TemplateResponse(
        "orders/payment_row.html",
        {"request": request, "payment": payment, "tbody_id": tbody_id},
    )
    return set_htmx_toast(response, "Платёж сохранён")


@router.get("/payments/{payment_id}/edit", response_class=HTMLResponse)
async def edit_payment_form(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return HTMLResponse("Платёж не найден", status_code=404)
    return templates.TemplateResponse(
        "orders/payment_row_edit.html",
        {"request": request, "payment": payment},
    )


@router.get("/payments/{payment_id}/view", response_class=HTMLResponse)
async def view_payment_row(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return HTMLResponse("Платёж не найден", status_code=404)
    return templates.TemplateResponse(
        "orders/payment_row.html",
        {"request": request, "payment": payment},
    )


@router.put("/payments/{payment_id}", response_class=HTMLResponse)
async def update_payment(
    payment_id: int,
    request: Request,
    payment_date: str = Form(""),
    amount: float = Form(...),
    currency: str = Form("RUB"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return HTMLResponse("Платёж не найден", status_code=404)

    parsed = _parse_date(payment_date)
    if parsed:
        payment.month = parsed.month
        payment.year = parsed.year
        payment.payment_day = parsed.day
    payment.amount = amount
    payment.currency = currency
    payment.amount_rub = round(await currency_service.convert_to_rub(amount, currency), 2)
    payment.notes = notes or None
    db.commit()
    db.refresh(payment)

    response = templates.TemplateResponse(
        "orders/payment_row.html",
        {"request": request, "payment": payment},
    )
    return set_htmx_toast(response, "Платёж обновлён")


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
    current_url = (request.headers.get("HX-Current-URL") or "").rstrip("/")
    detail_mode = f"/orders/{payment.client_id}" in current_url
    template_name = "orders/payment_toggle.html" if not detail_mode else "orders/payment_detail_toggle.html"
    response = templates.TemplateResponse(
        template_name,
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
    return set_htmx_toast(response, "Платёж удалён")
