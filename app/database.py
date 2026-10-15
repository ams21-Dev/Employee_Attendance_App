"""
database.py – Async MongoDB connection using Motor.

Motor is the async driver for MongoDB. It lets FastAPI handle many
concurrent requests without blocking while waiting for DB responses.
"""

import motor.motor_asyncio
from app.config import settings

# Motor creates one async client and reuses it across all requests.
# This is the recommended pattern – avoid creating a new client per request.
client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URI)

# The database object we import throughout the application
db = client[settings.DB_NAME]

# ---------------------------------------------------------------------------
# Collection helpers – thin wrappers so routers never hardcode string names
# ---------------------------------------------------------------------------

def attendance_collection():
    """Returns the 'attendance_records' collection."""
    return db["attendance_records"]


def audit_collection():
    """Returns the 'audit_logs' collection."""
    return db["audit_logs"]
