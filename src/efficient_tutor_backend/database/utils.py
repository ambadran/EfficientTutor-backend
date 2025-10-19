'''

'''
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..common.logger import log

async def get_enum_labels_async(db: AsyncSession, type_name: str) -> list[str]:
    """
    Dynamically fetches the labels for a given PostgreSQL ENUM type asynchronously.
    """
    log.info(f"Fetching labels for ENUM type '{type_name}'...")
    query = text("""
        SELECT e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = :type_name
        ORDER BY e.enumsortorder;
    """)
    try:
        result = await db.execute(query, {"type_name": type_name})
        labels = [row[0] for row in result.fetchall()]
        if not labels:
            raise ValueError(f"No labels found for ENUM type '{type_name}'.")
        log.info(f"Successfully fetched labels for '{type_name}': {labels}")
        return labels
    except Exception as e:
        log.error(f"Failed to fetch ENUM labels for '{type_name}': {e}", exc_info=True)
        raise
