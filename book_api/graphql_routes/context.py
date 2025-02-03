from book_api.database import get_db
from book_api.auth import get_current_active_user
from sqlalchemy.orm import Session
from fastapi import Request, Depends
from typing import Any, Dict

async def get_context(
    request: Request,
    db: Session = Depends(get_db),
    user: Any = Depends(get_current_active_user)
) -> Dict[str, Any]:
    return {
        "request": request,
        "db": db,
        "user": user
    }