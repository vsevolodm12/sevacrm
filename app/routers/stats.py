from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models.models import User
from app.services.stats import stats_service

router = APIRouter(prefix="/stats")
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
async def stats_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    monthly_history = stats_service.get_all_monthly_history(db)
    all_time = stats_service.get_all_time_totals(db)
    today = date.today()
    return templates.TemplateResponse(
        "stats/index.html",
        {
            "request": request,
            "current_user": current_user,
            "monthly_history": monthly_history,
            "all_time": all_time,
            "today": today,
        },
    )
