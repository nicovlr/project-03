"""API key authentication middleware."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("GOVSENSE_API_KEY")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """Validate the API key if one is configured.

    When GOVSENSE_API_KEY is not set, all requests are allowed (open mode).
    When set, requests must include a matching X-API-Key header.
    """
    if API_KEY is None:
        return None
    if key is None or key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return key
