from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.models import Client, Partner, Project, ProjectPayment, ProjectStatus, User

router = APIRouter(prefix="/projects")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def projects_index(
    request: Request,
    status_filter: str = "all",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Project)
    if status_filter != "all":
        try:
            status_enum = ProjectStatus(status_filter)
            query = query.filter(Project.status == status_enum)
        except ValueError:
            pass

    projects = query.order_by(Project.created_at.desc()).all()
    clients = db.query(Client).filter(Client.is_active == True).all()
    partners = db.query(Partner).filter(Partner.is_active == True).all()

    return templates.TemplateResponse(
        "projects/index.html",
        {
            "request": request,
            "current_user": current_user,
            "projects": projects,
            "clients": clients,
            "partners": partners,
            "status_filter": status_filter,
            "ProjectStatus": ProjectStatus,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_project(
    request: Request,
    title: str = Form(...),
    client_id: str = Form(""),
    partner_id: str = Form(""),
    status: str = Form("new"),
    total_amount: float = Form(0),
    advance_amount: float = Form(0),
    my_share: float = Form(0),
    currency: str = Form("RUB"),
    start_date: str = Form(""),
    end_date: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p_id = int(partner_id) if partner_id else None
    c_id = int(client_id) if client_id else None

    # Auto-calculate my_share if not provided
    if my_share == 0 and total_amount > 0:
        my_share = total_amount * 0.5 if p_id else total_amount

    project = Project(
        title=title,
        client_id=c_id,
        partner_id=p_id,
        status=ProjectStatus(status),
        total_amount=total_amount,
        advance_amount=advance_amount,
        my_share=my_share,
        currency=currency,
        start_date=datetime.strptime(start_date, "%Y-%m-%d") if start_date else None,
        end_date=datetime.strptime(end_date, "%Y-%m-%d") if end_date else None,
        notes=notes or None,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    response = templates.TemplateResponse(
        "projects/card.html",
        {
            "request": request,
            "project": project,
            "ProjectStatus": ProjectStatus,
        },
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Проект создан", "type": "success"}}'
    return response


@router.get("/{project_id}", response_class=HTMLResponse)
async def project_detail(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return HTMLResponse("Проект не найден", status_code=404)

    payments = (
        db.query(ProjectPayment)
        .filter(ProjectPayment.project_id == project_id)
        .order_by(ProjectPayment.created_at.desc())
        .all()
    )
    clients = db.query(Client).filter(Client.is_active == True).all()
    partners = db.query(Partner).filter(Partner.is_active == True).all()

    total_paid = sum(float(p.amount) for p in payments if p.is_paid)
    total_pending = sum(float(p.amount) for p in payments if not p.is_paid)

    return templates.TemplateResponse(
        "projects/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "project": project,
            "payments": payments,
            "clients": clients,
            "partners": partners,
            "total_paid": total_paid,
            "total_pending": total_pending,
            "ProjectStatus": ProjectStatus,
        },
    )


@router.get("/{project_id}/edit", response_class=HTMLResponse)
async def edit_project_form(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return HTMLResponse("Проект не найден", status_code=404)
    clients = db.query(Client).all()
    partners = db.query(Partner).filter(Partner.is_active == True).all()
    return templates.TemplateResponse(
        "projects/form.html",
        {
            "request": request,
            "project": project,
            "clients": clients,
            "partners": partners,
            "ProjectStatus": ProjectStatus,
        },
    )


@router.put("/{project_id}", response_class=HTMLResponse)
async def update_project(
    project_id: int,
    request: Request,
    title: str = Form(...),
    client_id: str = Form(""),
    partner_id: str = Form(""),
    status: str = Form("new"),
    total_amount: float = Form(0),
    advance_amount: float = Form(0),
    my_share: float = Form(0),
    currency: str = Form("RUB"),
    start_date: str = Form(""),
    end_date: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return HTMLResponse("Проект не найден", status_code=404)

    p_id = int(partner_id) if partner_id else None

    project.title = title
    project.client_id = int(client_id) if client_id else None
    project.partner_id = p_id
    project.status = ProjectStatus(status)
    project.total_amount = total_amount
    project.advance_amount = advance_amount
    project.my_share = my_share
    project.currency = currency
    project.start_date = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    project.end_date = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
    project.notes = notes or None
    db.commit()
    db.refresh(project)

    response = templates.TemplateResponse(
        "projects/card.html",
        {
            "request": request,
            "project": project,
            "ProjectStatus": ProjectStatus,
        },
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Проект обновлён", "type": "success"}}'
    return response


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        db.delete(project)
        db.commit()
    response = Response(content="", status_code=200)
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Проект удалён", "type": "success"}}'
    return response


@router.post("/{project_id}/payments", response_class=HTMLResponse)
async def create_project_payment(
    project_id: int,
    request: Request,
    payment_type: str = Form("partial"),
    amount: float = Form(...),
    currency: str = Form("RUB"),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return HTMLResponse("Проект не найден", status_code=404)

    payment = ProjectPayment(
        project_id=project_id,
        payment_type=payment_type,
        amount=amount,
        currency=currency,
        notes=notes or None,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    response = templates.TemplateResponse(
        "projects/payment_row.html",
        {"request": request, "payment": payment},
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Платёж добавлен", "type": "success"}}'
    return response


@router.put("/payments/{payment_id}/toggle", response_class=HTMLResponse)
async def toggle_project_payment(
    payment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(ProjectPayment).filter(ProjectPayment.id == payment_id).first()
    if not payment:
        return HTMLResponse("Платёж не найден", status_code=404)

    payment.is_paid = not payment.is_paid
    payment.paid_at = datetime.utcnow() if payment.is_paid else None
    db.commit()
    db.refresh(payment)

    response = templates.TemplateResponse(
        "projects/payment_row.html",
        {"request": request, "payment": payment},
    )
    return response
