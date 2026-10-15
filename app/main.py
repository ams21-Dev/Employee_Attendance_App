"""
main.py – FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app instance.
  - Register all routers.
  - Create MongoDB indexes on startup so queries are always fast.
  - Provide a health-check root endpoint.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import attendance_collection, audit_collection
from app.routers import analytics, attendance


# ---------------------------------------------------------------------------
# Lifespan: runs startup/shutdown code without deprecated @app.on_event
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Create indexes when the server starts.

    Indexes make queries fast. Without them MongoDB does a full collection scan
    on every request, which is very slow at scale.
    """
    att_col = attendance_collection()
    audit_col = audit_collection()

    # Composite index: quickly find an employee's active record (punch-in check)
    await att_col.create_index(
        [("employee_id", 1), ("status", 1)], name="employee_status_idx"
    )
    # Index on punch_in time: speeds up date-range queries in analytics
    await att_col.create_index([("punch_in", 1)], name="punch_in_idx")

    # Index so audit lookups by record_id are fast
    await audit_col.create_index([("record_id", 1)], name="audit_record_idx")

    yield  # application runs here

    # Shutdown logic (if needed) goes after yield
    # e.g., close connections – Motor handles this automatically


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="HROne – Employee Attendance & Analytics API",
    description=(
        "Punch-in / Punch-out management with business rule validation, "
        "immutable audit trails, and MongoDB-powered analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(attendance.router)
app.include_router(analytics.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def root():
    """Simple liveness probe – returns 200 OK when the server is running."""
    return {"status": "ok", "message": "HROne Attendance API is running."}
