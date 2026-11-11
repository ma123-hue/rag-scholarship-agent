from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.policy_file import PolicyFile
from app.models.user import User
from app.schemas.admin import PolicyFileRead, RebuildResponse
from ingest import rebuild_knowledge_base


router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _normalize_suffix(filename: str) -> str:
    return Path(filename).suffix.lower()


def _safe_storage_name(original_filename: str) -> str:
    suffix = _normalize_suffix(original_filename)
    stem = Path(original_filename).stem.strip().replace(" ", "_")
    stem = stem[:80] or "policy"
    return f"{stem}_{uuid4().hex[:10]}{suffix}"


@router.get("/files", response_model=list[PolicyFileRead])
def list_policy_files(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PolicyFile]:
    stmt = select(PolicyFile).order_by(PolicyFile.created_at.desc(), PolicyFile.id.desc())
    return list(db.execute(stmt).scalars().all())


@router.post("/files", response_model=PolicyFileRead, status_code=status.HTTP_201_CREATED)
async def upload_policy_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PolicyFile:
    settings = get_settings()
    policy_dir = settings.resolved_policy_dir
    policy_dir.mkdir(parents=True, exist_ok=True)

    suffix = _normalize_suffix(file.filename or "")
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pdf, .docx, and .txt files are supported",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    storage_name = _safe_storage_name(file.filename or "policy")
    storage_path = policy_dir / storage_name
    storage_path.write_bytes(content)

    record = PolicyFile(
        filename=storage_name,
        original_filename=file.filename or storage_name,
        file_type=suffix.lstrip("."),
        size_bytes=len(content),
        uploaded_by=current_user.username,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy_file(
    file_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    record = db.get(PolicyFile, file_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file_path = settings.resolved_policy_dir / record.filename
    if file_path.exists():
        file_path.unlink()

    db.delete(record)
    db.commit()


@router.post("/rebuild", response_model=RebuildResponse)
def rebuild_policy_index(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RebuildResponse:
    settings = get_settings()
    policy_dir = settings.resolved_policy_dir
    if not policy_dir.exists():
        raise HTTPException(status_code=404, detail="Policy directory not found")

    files_exist = db.execute(select(PolicyFile.id).limit(1)).first()
    if not files_exist:
        raise HTTPException(status_code=400, detail="No managed policy files found")

    try:
        document_count, chunk_count = rebuild_knowledge_base(policy_dir)
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document parser dependency missing: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Knowledge base rebuild failed: {exc}",
        ) from exc

    return RebuildResponse(
        detail="Knowledge base rebuilt successfully",
        document_count=document_count,
        chunk_count=chunk_count,
    )
