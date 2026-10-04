"""
SecureStego — MongoDB Audit Trail

Full implementation using motor (async MongoDB driver).

Design rationale — why BOTH Postgres and MongoDB?

  Postgres (primary):
    - Relational integrity for users and operations.
    - Strong schema enforcement, foreign keys, transactions.
    - The authoritative source of truth for auth and operational data.

  MongoDB (audit mirror):
    - Distributed, schema-flexible audit trail.
    - Every Operation write is mirrored here asynchronously.
    - MongoDB's replica set architecture enables geographic distribution
      of audit data independently from the primary Postgres database.
    - Schema-flexible: audit entries can evolve (add fields, change structure)
      without migration friction — useful for an audit log where the schema
      of "what we want to record" may change over time.
    - In production: MongoDB Atlas free-tier replica set provides automatic
      replication across 3 nodes. Locally: a single mongod via docker-compose.

The audit mirror is fire-and-forget — if MongoDB is down, the operation
still succeeds (Postgres is the source of truth). MongoDB failures are
logged but do not propagate to the API response.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level client — initialized lazily on first use
_mongo_client = None
_mongo_db = None


def _get_mongo_db():
    """Get the MongoDB database client (lazy initialization).

    Returns None if MongoDB is not enabled or not reachable.
    """
    global _mongo_client, _mongo_db

    if not settings.mongo_enabled:
        return None

    if _mongo_db is not None:
        return _mongo_db

    try:
        from motor.motor_asyncio import AsyncIOMotorClient

        _mongo_client = AsyncIOMotorClient(
            settings.mongo_url,
            serverSelectionTimeoutMS=3000,  # Fail fast if Mongo is down
        )
        _mongo_db = _mongo_client[settings.mongo_db_name]
        logger.info("MongoDB audit trail connected: %s", settings.mongo_url)
        return _mongo_db
    except Exception as e:
        logger.warning("MongoDB audit trail unavailable: %s", e)
        return None


async def mirror_operation_to_mongo(operation_data: dict[str, Any]) -> bool:
    """Mirror an Operation record to the MongoDB audit collection.

    Fire-and-forget: if MongoDB is unavailable, the operation still succeeds.
    Failures are logged but not propagated.

    Args:
        operation_data: Dictionary representation of the Operation record.

    Returns:
        True if successfully written, False if skipped or failed.
    """
    db = _get_mongo_db()
    if db is None:
        logger.debug(
            "MongoDB audit mirror disabled/unavailable — skipping operation_id=%s",
            operation_data.get("operation_id", "unknown"),
        )
        return False

    try:
        collection = db["operations"]
        # Add audit-specific metadata
        audit_entry = {
            **operation_data,
            "mirrored_at": datetime.now(timezone.utc).isoformat(),
            "source": "postgres_mirror",
        }
        result = await collection.insert_one(audit_entry)
        logger.info(
            "MongoDB audit: mirrored operation_id=%s → mongo_id=%s",
            operation_data.get("operation_id", "unknown"),
            result.inserted_id,
        )
        return True
    except Exception as e:
        # Fire-and-forget — log but don't propagate
        logger.warning(
            "MongoDB audit mirror failed for operation_id=%s: %s",
            operation_data.get("operation_id", "unknown"),
            e,
        )
        return False


async def get_audit_trail(
    operation_id: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 50,
) -> list[dict]:
    """Query the MongoDB audit trail.

    Args:
        operation_id: Filter by specific operation ID.
        user_id: Filter by sender user ID.
        limit: Max number of results.

    Returns:
        List of audit entries (dicts). Empty list if MongoDB is unavailable.
    """
    db = _get_mongo_db()
    if db is None:
        return []

    try:
        collection = db["operations"]
        query: dict[str, Any] = {}
        if operation_id:
            query["operation_id"] = operation_id
        if user_id:
            query["sender_id"] = user_id

        cursor = collection.find(query).sort("mirrored_at", -1).limit(limit)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
            results.append(doc)
        return results
    except Exception as e:
        logger.warning("MongoDB audit query failed: %s", e)
        return []


async def close_mongo_client() -> None:
    """Close the MongoDB client connection (for shutdown)."""
    global _mongo_client, _mongo_db
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("MongoDB client closed.")
