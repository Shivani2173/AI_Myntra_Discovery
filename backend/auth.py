from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, status

from backend.config import Settings, get_settings


def require_ingest_token(
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.ingest_token
    if not x_ingest_token or not expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ingest token")
    if not secrets.compare_digest(x_ingest_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ingest token")
