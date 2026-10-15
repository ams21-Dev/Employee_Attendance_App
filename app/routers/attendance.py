"""
attendance.py – Punch-In, Punch-Out, and Manual Correction endpoints.

Business rules enforced here:
  1. An employee cannot punch in if they already have an active (open) record.
  2. Punch-out time must be after punch-in time.
  3. Total hours worked is calculated automatically on punch-out.
  4. Every manual correction is recorded in the audit_logs collection.
"""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status

from app.database import attendance_collection, audit_collection
from app.models import (
    AttendanceResponse,
    AuditLogResponse,
    CorrectionRequest,
    PunchInRequest,
    PunchOutRequest,
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc: dict) -> dict:
    """Convert MongoDB _id (ObjectId) to a plain string for JSON responses."""
    doc["id"] = str(doc.pop("_id"))
    return doc


# ---------------------------------------------------------------------------
# POST /attendance/punch-in
# ---------------------------------------------------------------------------

@router.post("/punch-in", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def punch_in(payload: PunchInRequest):
    """
    Record a punch-in for an employee.

    Rejects the request if the employee already has an open shift (status='active'),
    preventing the classic 'double punch-in' problem.
    """
    col = attendance_collection()

    # --- Business Rule 1: No duplicate active punch-in ---
    active = await col.find_one(
        {"employee_id": payload.employee_id, "status": "active"}
    )
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee '{payload.employee_id}' is already punched in. Punch out first.",
        )

    doc: dict[str, Any] = {
        "employee_id": payload.employee_id,
        "punch_in": payload.punch_in,
        "punch_out": None,
        "total_hours": None,
        "status": "active",
        "notes": payload.notes,
    }

    result = await col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


# ---------------------------------------------------------------------------
# POST /attendance/punch-out
# ---------------------------------------------------------------------------

@router.post("/punch-out", response_model=AttendanceResponse)
async def punch_out(payload: PunchOutRequest):
    """
    Record a punch-out for an employee.

    Finds the open shift for this employee and closes it, computing total hours.
    """
    col = attendance_collection()

    # Find the currently active record for this employee
    record = await col.find_one(
        {"employee_id": payload.employee_id, "status": "active"}
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active punch-in found for employee '{payload.employee_id}'.",
        )

# --- Business Rule 2: Punch-out must be after punch-in ---
    punch_in_time = record["punch_in"]
    punch_out_time = payload.punch_out

    # Make punch_out offset-aware if punch_in from MongoDB has timezone info
    if punch_in_time.tzinfo is not None and punch_out_time.tzinfo is None:
        from datetime import timezone
        punch_out_time = punch_out_time.replace(tzinfo=timezone.utc)
    elif punch_in_time.tzinfo is None and punch_out_time.tzinfo is not None:
        punch_out_time = punch_out_time.replace(tzinfo=None)

    if punch_out_time <= punch_in_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Punch-out time must be after punch-in time.",
        )

    # --- Business Rule 3: Calculate total hours worked ---
    delta = punch_out_time - punch_in_time
    total_hours = round(delta.total_seconds() / 3600, 2)

    # Update the document in place
    update = {
        "punch_out": punch_out_time,
        "total_hours": total_hours,
        "status": "completed",
    }
    await col.update_one({"_id": record["_id"]}, {"$set": update})

    record.update(update)
    return _serialize(record)

# ---------------------------------------------------------------------------
# GET /attendance/{employee_id}
# ---------------------------------------------------------------------------

@router.get("/{employee_id}", response_model=list[AttendanceResponse])
async def get_employee_attendance(employee_id: str):
    """Return all attendance records for a given employee (newest first)."""
    col = attendance_collection()
    cursor = col.find({"employee_id": employee_id}).sort("punch_in", -1)
    records = [_serialize(doc) async for doc in cursor]
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No records found for employee '{employee_id}'.",
        )
    return records


# ---------------------------------------------------------------------------
# PATCH /attendance/correct
# ---------------------------------------------------------------------------

@router.patch("/correct", response_model=AttendanceResponse)
async def correct_attendance(payload: CorrectionRequest):
    """
    Manually correct a punch record (admin only in production).

    Steps:
      1. Fetch the existing record.
      2. Store the original data in audit_logs (immutable trail).
      3. Apply the corrections and recompute total_hours if both times are set.
      4. Return the updated record.
    """
    col = attendance_collection()
    audit_col = audit_collection()

    # Validate the provided record_id
    try:
        object_id = ObjectId(payload.record_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid record_id format.",
        )

    record = await col.find_one({"_id": object_id})
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance record '{payload.record_id}' not found.",
        )

    # Build the update dict from only the fields explicitly provided
    changes: dict[str, Any] = {}
    if payload.punch_in is not None:
        changes["punch_in"] = payload.punch_in
    if payload.punch_out is not None:
        changes["punch_out"] = payload.punch_out
    if payload.notes is not None:
        changes["notes"] = payload.notes

    # Recompute total_hours if both timestamps are now known
    final_punch_in = changes.get("punch_in", record.get("punch_in"))
    final_punch_out = changes.get("punch_out", record.get("punch_out"))

    if final_punch_in and final_punch_out:
        if final_punch_out <= final_punch_in:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Corrected punch-out must still be after punch-in.",
            )
        delta = final_punch_out - final_punch_in
        changes["total_hours"] = round(delta.total_seconds() / 3600, 2)
        changes["status"] = "completed"

    # --- Audit Trail: save original data BEFORE making changes ---
    # The original_data snapshot is immutable once inserted.
    original_snapshot = {k: str(v) if isinstance(v, ObjectId) else v for k, v in record.items()}
    original_snapshot.pop("_id", None)

    audit_doc = {
        "record_id": payload.record_id,
        "edited_by": payload.edited_by,
        "reason": payload.reason,
        "original_data": original_snapshot,
        "updated_data": {k: str(v) if isinstance(v, datetime) else v for k, v in changes.items()},
        "timestamp": datetime.now(timezone.utc),
    }
    await audit_col.insert_one(audit_doc)

    # Apply corrections
    await col.update_one({"_id": object_id}, {"$set": changes})

    updated = await col.find_one({"_id": object_id})
    return _serialize(updated)


# ---------------------------------------------------------------------------
# GET /attendance/audit/{record_id}
# ---------------------------------------------------------------------------

@router.get("/audit/{record_id}", response_model=list[AuditLogResponse])
async def get_audit_logs(record_id: str):
    """Return all audit log entries for a given attendance record."""
    audit_col = audit_collection()
    cursor = audit_col.find({"record_id": record_id}).sort("timestamp", -1)
    logs = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        logs.append(doc)
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit logs found for record '{record_id}'.",
        )
    return logs
