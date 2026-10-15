# HROne – Employee Attendance & Analytics API

A production-ready REST API built with **FastAPI**, **Motor** (async MongoDB driver), and **Pydantic v2** for managing employee attendance with business-rule enforcement, immutable audit trails, and aggregation-powered analytics.

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- MongoDB running locally (`mongodb://localhost:27017`) **or** a MongoDB Atlas URI

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure (optional)
Set environment variables to override defaults:
```bash
# Windows PowerShell
$env:MONGO_URI = "mongodb://localhost:27017"
$env:DB_NAME   = "hrone_attendance"

# Linux / macOS
export MONGO_URI="mongodb://localhost:27017"
export DB_NAME="hrone_attendance"
```
Or create a `.env` file (never commit it):
```
MONGO_URI=mongodb://localhost:27017
DB_NAME=hrone_attendance
```

### 4. Run the Server
```bash
uvicorn app.main:app --reload
```
Server starts at → **http://127.0.0.1:8000**

### 5. Interactive API Docs
| UI | URL |
|---|---|
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |

---

## API Endpoints Summary

### Attendance

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/attendance/punch-in` | Record employee punch-in |
| `POST` | `/attendance/punch-out` | Record employee punch-out & compute hours |
| `GET` | `/attendance/{employee_id}` | List all records for an employee |
| `PATCH` | `/attendance/correct` | Admin manual correction with audit trail |
| `GET` | `/attendance/audit/{record_id}` | View audit history for a record |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/analytics/monthly-hours?year=2026&month=10` | Total hours per employee in a month |
| `GET` | `/analytics/late-arrivals?year=2026&month=10&cutoff_hour=9` | Late arrival count per employee |
| `GET` | `/analytics/avg-daily-hours` | Average daily hours per employee (all time) |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Liveness probe |

---

## Example Requests

**Punch In**
```bash
curl -X POST http://localhost:8000/attendance/punch-in \
  -H "Content-Type: application/json" \
  -d '{"employee_id": "E001", "punch_in": "2026-10-15T09:05:00+05:30"}'
```

**Punch Out**
```bash
curl -X POST http://localhost:8000/attendance/punch-out \
  -H "Content-Type: application/json" \
  -d '{"employee_id": "E001", "punch_out": "2026-10-15T18:00:00+05:30"}'
```

**Manual Correction**
```bash
curl -X PATCH http://localhost:8000/attendance/correct \
  -H "Content-Type: application/json" \
  -d '{
    "record_id": "<mongo_id>",
    "edited_by": "admin@hrone.com",
    "reason": "System recorded wrong time due to network lag",
    "punch_in": "2026-10-15T08:55:00+05:30"
  }'
```

---

## Project Structure
```
app/
├── main.py        # FastAPI app, startup indexes, router registration
├── config.py      # Settings via pydantic-settings
├── database.py    # Motor async client + collection helpers
├── models.py      # Pydantic v2 request/response schemas
└── routers/
    ├── attendance.py  # Punch-in, Punch-out, Corrections
    └── analytics.py   # Aggregation pipeline endpoints
```
