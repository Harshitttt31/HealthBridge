"""Upload endpoints (BRD §10, FR-02/03).

  POST /upload/ahc   (provider) -> validate + steps 1-3, store de-identified AHC per company
  POST /upload/hrms  (hr)       -> validate + steps 1-3, store de-identified HRMS

AHC is uploaded by a Health Provider who holds data for all companies in one
file. The pipeline splits the file by company_id and stores each slice
separately so /process can combine per company. HRMS uploads remain
company-scoped via the HR user's JWT.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session

from app.auth import CurrentUser, require_role
from app.db import get_session
from app.ingestion import check_tenant_isolation, validate
from app.models import Role, Upload, UploadKind, UploadStatus

_log = logging.getLogger(__name__)
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


async def _handle_upload_hrms(file: UploadFile, user: CurrentUser,
                              session: Session) -> dict:
    """HRMS upload: single-tenant authorization boundary.

    The file must contain exactly one distinct CUG value and it must match the
    HR user's tenant. Any deviation is an authorization violation: rejected
    outright, logged, no partial ingestion.
    """
    filename = file.filename or "upload"
    raw = await file.read()
    df, result = validate(raw, filename, UploadKind.hrms)

    if not result.ok or df is None:
        session.add(Upload(company_id=user.company_id, kind=UploadKind.hrms,
                           status=UploadStatus.failed, filename=filename,
                           message=result.message))
        session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=result.as_dict())

    # Authorization boundary: file CUG set must be exactly {tenant}.
    violation = check_tenant_isolation(df, user.company_id)
    if violation is not None:
        _log.warning(
            "HRMS tenant violation | user_id=%s tenant=%s filename=%r foreign_cugs=%s",
            user.user_id, user.company_id, filename, violation.foreign or violation.found,
        )
        msg = violation.message()
        session.add(Upload(company_id=user.company_id, kind=UploadKind.hrms,
                           status=UploadStatus.failed, filename=filename,
                           message=msg))
        session.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=msg)

    identifiers, noise_cols = _CONFIG[UploadKind.hrms]
    df = step1_deidentify(df, identifiers)
    df = step2_noise(df, noise_cols)
    df = step3_tokenize(df)
    df = df.drop(columns=[c for c in ["employee_id"] if c in df.columns])

    save_deident(user.company_id, UploadKind.hrms, df)

    notes = list(result.warnings)
    up = Upload(company_id=user.company_id, kind=UploadKind.hrms,
                status=UploadStatus.received, filename=filename,
                row_count=len(df), message="; ".join(notes) or result.message)
    session.add(up)
    session.commit()
    session.refresh(up)

    return {
        "upload_id": up.id,
        "kind": UploadKind.hrms.value,
        "company_id": user.company_id,
        "rows_stored": len(df),
        "warnings": notes,
    }


async def _handle_upload_ahc(file: UploadFile, session: Session) -> dict:
    """AHC upload: provider uploads data for all companies in one file.

    Splits by company_id and stores each slice independently so /process can
    pair each company's AHC with its HRMS upload.
    """
    raw = await file.read()
    df, result = validate(raw, file.filename or "upload", UploadKind.ahc)

    if not result.ok or df is None:
        session.add(Upload(company_id="provider", kind=UploadKind.ahc,
                           status=UploadStatus.failed, filename=file.filename,
                           message=result.message))
        session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=result.as_dict())

    identifiers, noise_cols = _CONFIG[UploadKind.ahc]

    rows_stored = 0
    companies_stored: list[str] = []
    notes = list(result.warnings)

    for company_id, slice_df in df.groupby(COMPANY_ID):
        company_id = str(company_id)
        s = step1_deidentify(slice_df.copy(), identifiers)
        s = step2_noise(s, noise_cols)
        s = step3_tokenize(s)
        s = s.drop(columns=[c for c in ["employee_id"] if c in s.columns])
        save_deident(company_id, UploadKind.ahc, s)
        rows_stored += len(s)
        companies_stored.append(company_id)

        up = Upload(company_id=company_id, kind=UploadKind.ahc,
                    status=UploadStatus.received, filename=file.filename,
                    row_count=len(s), message=result.message)
        session.add(up)

    session.commit()

    return {
        "kind": UploadKind.ahc.value,
        "companies_stored": companies_stored,
        "rows_stored": rows_stored,
        "warnings": notes,
    }


@router.post("/ahc")
async def upload_ahc(file: UploadFile = File(...),
                     _user: CurrentUser = Depends(require_role(Role.provider)),
                     session: Session = Depends(get_session)) -> dict:
    return await _handle_upload_ahc(file, session)


@router.post("/hrms")
async def upload_hrms(file: UploadFile = File(...),
                      user: CurrentUser = Depends(require_role(Role.hr)),
                      session: Session = Depends(get_session)) -> dict:
    return await _handle_upload_hrms(file, user, session)
