from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.models import Client, Partner, Project, User

router = APIRouter(prefix="/partners")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def partners_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partners = db.query(Partner).order_by(Partner.name).all()
    partners_data = []
    for partner in partners:
        clients_count = db.query(Client).filter(Client.partner_id == partner.id).count()
        projects_count = db.query(Project).filter(Project.partner_id == partner.id).count()
        partners_data.append({
            "partner": partner,
            "clients_count": clients_count,
            "projects_count": projects_count,
        })
    return templates.TemplateResponse(
        "partners/index.html",
        {
            "request": request,
            "current_user": current_user,
            "partners_data": partners_data,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_partner(
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    telegram: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = Partner(
        name=name,
        phone=phone or None,
        telegram=telegram or None,
    )
    db.add(partner)
    db.commit()
    db.refresh(partner)

    clients_count = 0
    projects_count = 0

    response = templates.TemplateResponse(
        "partners/card.html",
        {
            "request": request,
            "partner": partner,
            "clients_count": clients_count,
            "projects_count": projects_count,
        },
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Партнёр добавлен", "type": "success"}}'
    return response


@router.get("/{partner_id}/edit", response_class=HTMLResponse)
async def edit_partner_form(
    partner_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        return HTMLResponse("Партнёр не найден", status_code=404)
    return templates.TemplateResponse(
        "partners/form.html",
        {"request": request, "partner": partner},
    )


@router.put("/{partner_id}", response_class=HTMLResponse)
async def update_partner(
    partner_id: int,
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    telegram: str = Form(""),
    is_active: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if not partner:
        return HTMLResponse("Партнёр не найден", status_code=404)

    partner.name = name
    partner.phone = phone or None
    partner.telegram = telegram or None
    partner.is_active = is_active == "on"
    db.commit()
    db.refresh(partner)

    clients_count = db.query(Client).filter(Client.partner_id == partner.id).count()
    projects_count = db.query(Project).filter(Project.partner_id == partner.id).count()

    response = templates.TemplateResponse(
        "partners/card.html",
        {
            "request": request,
            "partner": partner,
            "clients_count": clients_count,
            "projects_count": projects_count,
        },
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Партнёр обновлён", "type": "success"}}'
    return response


@router.delete("/{partner_id}")
async def delete_partner(
    partner_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if partner:
        db.delete(partner)
        db.commit()
    response = Response(content="", status_code=200)
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Партнёр удалён", "type": "success"}}'
    return response
