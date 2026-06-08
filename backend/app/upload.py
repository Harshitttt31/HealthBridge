"""Upload endpoints (BRD §10, FR-02/03).

  POST /upload/ahc   (employer) -> validate + steps 1-3, store de-identified AHC
  POST /upload/hrms  (hr)       -> validate + steps 1-3, store de-identified HRMS

Each upload is scoped to the caller's company_id (FR-05 isolation): rows for
other companies in the file are dropped and reported. The stored set is
identifier-free (employee_id replaced by its token).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.auth import CurrentUser, require_role
from app.db import get_session
from app.ingestion import validate
from app.models import Role, Upload, UploadKind, UploadStatus
from app.pipeline import (
    AHC_IDENTIFIERS, AHC_NOISE_COLS, HRMS_IDENTIFIERS, HRMS_NOISE_COLS,
    step1_deidentify, step2_noise, step3_tokenize,
)
from app.pipeline.companies import COMPANY_ID
from app.storage import save_deident

router = APIRouter(prefix="/upload", tags=["upload"])

_CONFIG = {
    UploadKind.ahc: (AHC_IDENTIFIERS, AHC_NOISE_COLS),
    UploadKind.hrms: (HRMS_IDENTIFIERS, HRMS_NOISE_COLS),
}


async def _handle_upload(kind: UploadKind, file: UploadFile, user: CurrentUser,
                         session: Session) -> dict:
    raw = await file.read()
    df, result = validate(raw, file.filename or "upload", kind)

    if not result.ok or df is None:
        # Record the failed attempt, then 422 with the validation detail.
        session.add(Upload(company_id=user.company_id, kind=kind,
                           status=UploadStatus.failed, filename=file.filename,
                           message=result.message))
        session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=result.as_dict())

    # Company isolation: keep only the uploader's company.
    total = len(df)
    df = df[df[COMPANY_ID] == user.company_id]
    other = total - len(df)
    if df.empty:
        msg = (f"No rows for your company ({user.company_id}); "
               f"file contained {result.company_ids}.")
        session.add(Upload(company_id=user.company_id, kind=kind,
                           status=UploadStatus.failed, filename=file.filename,
                           message=msg))
        session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

    # Steps 1-3: de-identify -> noise -> tokenize, then drop employee_id.
    identifiers, noise_cols = _CONFIG[kind]
    df = step1_deidentify(df, identifiers)
    df = step2_noise(df, noise_cols)
    df = step3_tokenize(df)
    df = df.drop(columns=[c for c in ["employee_id"] if c in df.columns])

    save_deident(user.company_id, kind, df)

    notes = list(result.warnings)
    if other:
        notes.append(f"Dropped {other} row(s) for other companies (isolation).")
    up = Upload(company_id=user.company_id, kind=kind,
                status=UploadStatus.received, filename=file.filename,
                row_count=len(df), message="; ".join(notes) or result.message)
    session.add(up)
    session.commit()
    session.refresh(up)

    return {
        "upload_id": up.id,
        "kind": kind.value,
        "company_id": user.company_id,
        "rows_stored": len(df),
        "rows_dropped_other_company": other,
        "warnings": notes,
    }


@router.post("/ahc")
async def upload_ahc(file: UploadFile = File(...),
                     user: CurrentUser = Depends(require_role(Role.employer)),
                     session: Session = Depends(get_session)) -> dict:
    return await _handle_upload(UploadKind.ahc, file, user, session)


@router.post("/hrms")
async def upload_hrms(file: UploadFile = File(...),
                      user: CurrentUser = Depends(require_role(Role.hr)),
                      session: Session = Depends(get_session)) -> dict:
    return await _handle_upload(UploadKind.hrms, file, user, session)
