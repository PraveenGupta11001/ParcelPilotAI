from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.auth.deps import RoleChecker
from app.tools.proactive_signals import get_operational_signals

router = APIRouter(tags=["insights"])

@router.get("/insights")
def insights(
    current_user: User = Depends(RoleChecker(["internal_support", "internal_lead"])),
    db: Session = Depends(get_db)
):
    """Retrieves operational insights and customer service signals analytics.

    Enforces support staff or manager role validation (internal_support, internal_lead).

    Args:
        current_user: Authenticated staff user object.
        db: Database session.

    Returns:
        dict: Statistical insights mapping ticket counts, SLA warnings, and anomalies.
    """
    stats = get_operational_signals(db, current_user)
    return stats
