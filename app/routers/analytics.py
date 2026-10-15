"""
analytics.py – Analytics endpoints powered by MongoDB aggregation pipelines.

Each endpoint runs a focused aggregation pipeline using:
  $match  – filter the documents we care about
  $group  – aggregate / sum / average grouped by a key
  $project – shape the output

These pipelines are kept intentionally simple so they are easy to explain.
"""

from fastapi import APIRouter, HTTPException, status

from app.database import attendance_collection
from app.models import DailyAvgResponse, LateArrivalResponse, MonthlyHoursResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ---------------------------------------------------------------------------
# GET /analytics/monthly-hours
# ---------------------------------------------------------------------------

@router.get("/monthly-hours", response_model=list[MonthlyHoursResponse])
async def monthly_hours(year: int, month: int):
    """
    Total hours worked per employee for a given year/month.

    Pipeline stages:
      1. $match  – keep only completed records in the requested month.
      2. $group  – sum total_hours per employee.
      3. $project – reshape output fields.
    """
    col = attendance_collection()

    pipeline = [
        # Stage 1 – filter: only completed records, correct year & month
        {
            "$match": {
                "status": "completed",
                "total_hours": {"$ne": None},
                "$expr": {
                    "$and": [
                        {"$eq": [{"$year": "$punch_in"}, year]},
                        {"$eq": [{"$month": "$punch_in"}, month]},
                    ]
                },
            }
        },
        # Stage 2 – group by employee and sum their hours
        {
            "$group": {
                "_id": "$employee_id",
                "total_hours": {"$sum": "$total_hours"},
            }
        },
        # Stage 3 – rename _id to employee_id and add year/month
        {
            "$project": {
                "_id": 0,
                "employee_id": "$_id",
                "year": {"$literal": year},
                "month": {"$literal": month},
                "total_hours": {"$round": ["$total_hours", 2]},
            }
        },
    ]

    results = await col.aggregate(pipeline).to_list(length=None)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed records found for {year}-{month:02d}.",
        )
    return results


# ---------------------------------------------------------------------------
# GET /analytics/late-arrivals
# ---------------------------------------------------------------------------

@router.get("/late-arrivals", response_model=list[LateArrivalResponse])
async def late_arrivals(year: int, month: int, cutoff_hour: int = 9):
    """
    Count how many times each employee arrived late in a given month.

    'Late' is defined as punching in after cutoff_hour (default 09:00).

    Pipeline stages:
      1. $match  – completed records in the target month.
      2. $match  – punch_in hour is strictly greater than the cutoff.
      3. $group  – count late arrivals per employee.
      4. $project – rename and add context fields.
    """
    col = attendance_collection()

    pipeline = [
        # Stage 1 – scope to the right month
        {
            "$match": {
                "status": "completed",
                "$expr": {
                    "$and": [
                        {"$eq": [{"$year": "$punch_in"}, year]},
                        {"$eq": [{"$month": "$punch_in"}, month]},
                    ]
                },
            }
        },
        # Stage 2 – keep only days where they punched in after cutoff_hour
        {
            "$match": {
                "$expr": {"$gt": [{"$hour": "$punch_in"}, cutoff_hour - 1]}
            }
        },
        # Stage 3 – count late days per employee
        {
            "$group": {
                "_id": "$employee_id",
                "late_arrivals": {"$sum": 1},
            }
        },
        # Stage 4 – clean up output shape
        {
            "$project": {
                "_id": 0,
                "employee_id": "$_id",
                "year": {"$literal": year},
                "month": {"$literal": month},
                "late_arrivals": 1,
            }
        },
    ]

    results = await col.aggregate(pipeline).to_list(length=None)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No late-arrival data for {year}-{month:02d}.",
        )
    return results


# ---------------------------------------------------------------------------
# GET /analytics/avg-daily-hours
# ---------------------------------------------------------------------------

@router.get("/avg-daily-hours", response_model=list[DailyAvgResponse])
async def avg_daily_hours():
    """
    Average daily working hours per employee across all completed records.

    Pipeline stages:
      1. $match  – only completed records with a real total_hours value.
      2. $group  – compute average hours per employee.
      3. $project – rename and round.
    """
    col = attendance_collection()

    pipeline = [
        # Stage 1 – only records that have a computed hours value
        {
            "$match": {
                "status": "completed",
                "total_hours": {"$ne": None, "$gt": 0},
            }
        },
        # Stage 2 – average hours per employee (each document = one day's shift)
        {
            "$group": {
                "_id": "$employee_id",
                "average_daily_hours": {"$avg": "$total_hours"},
            }
        },
        # Stage 3 – shape the response
        {
            "$project": {
                "_id": 0,
                "employee_id": "$_id",
                "average_daily_hours": {"$round": ["$average_daily_hours", 2]},
            }
        },
    ]

    results = await col.aggregate(pipeline).to_list(length=None)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed attendance records found.",
        )
    return results
