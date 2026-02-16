from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AuditLog

async def log_action(
    db: AsyncSession,
    user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    ip_address: Optional[str] = None
):
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address
    )
    db.add(log_entry)
    # Note: Usually we commit here, or rely on caller to commit.
    # To be safe and ensure logs persist even if subsequent logic fails (though async session usually commits at end of transaction unit),
    # we might want a separate session or commit immediately.
    # However, for consistency within a transaction, we leave it to the caller's transaction scope unless specified otherwise.
    # But usually audit logs should persist even on failure of other things?
    # For now, let's assume it's part of the same transaction.
    return log_entry
