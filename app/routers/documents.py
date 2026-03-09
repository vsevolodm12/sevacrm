import os
import re
from datetime import datetime

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models.models import Document, User

router = APIRouter(prefix="/documents")
templates = Jinja2Templates(directory="app/templates")

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def secure_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = re.sub(r"[^\w\s\-.]", "_", filename)
    filename = re.sub(r"\s+", "_", filename)
    return filename or "file"


@router.post("/upload", response_class=HTMLResponse)
async def upload_document(
    request: Request,
    title: str = Form(""),
    doc_type: str = Form("other"),
    project_id: str = Form(""),
    client_id: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return HTMLResponse(
            f"<div class='text-red-500'>Недопустимый тип файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}</div>",
            status_code=400,
        )

    # Read file to check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return HTMLResponse(
            "<div class='text-red-500'>Файл слишком большой. Максимум 50 МБ.</div>",
            status_code=400,
        )

    title = title or os.path.splitext(file.filename or "file")[0]

    # Build storage path: uploads/{year}/{month}/{timestamp}_{filename}
    now = datetime.utcnow()
    safe_name = secure_filename(file.filename or "file")
    timestamp = int(now.timestamp())
    stored_filename = f"{timestamp}_{safe_name}"
    rel_dir = os.path.join(settings.upload_dir, str(now.year), str(now.month).zfill(2))
    os.makedirs(rel_dir, exist_ok=True)
    file_path = os.path.join(rel_dir, stored_filename)

    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(content)

    document = Document(
        title=title,
        project_id=int(project_id) if project_id else None,
        client_id=int(client_id) if client_id else None,
        doc_type=doc_type,
        file_path=file_path,
        file_name=file.filename or safe_name,
        file_size=len(content),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    response = templates.TemplateResponse(
        "partials/document_card.html",
        {"request": request, "document": document},
    )
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Документ загружен", "type": "success"}}'
    return response


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return HTMLResponse("Документ не найден", status_code=404)

    if not os.path.exists(document.file_path):
        return HTMLResponse("Файл не найден на сервере", status_code=404)

    return FileResponse(
        path=document.file_path,
        filename=document.file_name,
        media_type="application/octet-stream",
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if document:
        # Remove file from disk
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        db.delete(document)
        db.commit()
    response = Response(content="", status_code=200)
    response.headers["HX-Trigger"] = '{"showToast": {"message": "Документ удалён", "type": "success"}}'
    return response
