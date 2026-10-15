"""
models.py – Pydantic v2 request/response schemas.

Pydantic validates incoming JSON automatically and gives clear error messages
when data is missing or has the wrong type – no manual validation needed.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Attendance schemas
# ---------------------------------------------------------------------------

class PunchInRequest(BaseModel):
    employee_id: str = Field(..., description="Unique identifier of the employee")
    punch_in: datetime = Field(..., description="Punch-in timestamp (ISO 8601 with timezone)")
    notes: Optional[str] = Field(None, description="Optional notes for the shift")


class PunchOutRequest(BaseModel):
    employee_id: str = Field(..., description="Employee ID to punch out")
    punch_out: datetime = Field(..., description="Punch-out timestamp (ISO 8601 with timezone)")


class AttendanceResponse(BaseModel):
    """Shape of a single attendance record returned to the client."""
    id: str = Field(..., description="MongoDB document _id as string")
    employee_id: str
    punch_in: datetime
    punch_out: Optional[datetime] = None
    total_hours: Optional[float] = Field(None, description="Total hours worked, set on punch-out")
    status: str = Field(..., description="'active' while punched in, 'completed' after punch-out")
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Manual correction schemas
# ---------------------------------------------------------------------------

class CorrectionRequest(BaseModel):
    """Payload sent by an admin to correct a punch record."""
    record_id: str = Field(..., description="MongoDB _id of the attendance record to correct")
    edited_by: str = Field(..., description="Admin / manager who is making the correction")
    reason: str = Field(..., description="Mandatory business reason for the edit")
    punch_in: Optional[datetime] = Field(None, description="New punch-in time (optional)")
    punch_out: Optional[datetime] = Field(None, description="New punch-out time (optional)")
    notes: Optional[str] = Field(None, description="Updated notes (optional)")


# ---------------------------------------------------------------------------
# Audit log schema
# ---------------------------------------------------------------------------

class AuditLogResponse(BaseModel):
    """Shape of a single audit log entry."""
    id: str
    record_id: str
    edited_by: str
    reason: str
    original_data: dict[str, Any]
    updated_data: dict[str, Any]
    timestamp: datetime


# ---------------------------------------------------------------------------
# Analytics schemas
# ---------------------------------------------------------------------------

class MonthlyHoursResponse(BaseModel):
    employee_id: str
    year: int
    month: int
    total_hours: float


class LateArrivalResponse(BaseModel):
    employee_id: str
    year: int
    month: int
    late_arrivals: int


class DailyAvgResponse(BaseModel):
    employee_id: str
    average_daily_hours: float
