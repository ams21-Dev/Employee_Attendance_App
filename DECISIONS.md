# DECISIONS.md – Architectural & Design Decisions

This document explains the key technology and design choices made in the HROne Employee Attendance & Analytics API.

---

## 1. Why FastAPI?

**FastAPI** was chosen because:

- **High performance**: It is built on Starlette and uses Python's `async/await` model. Under load, an async endpoint can handle thousands of concurrent requests without spawning OS threads.
- **Automatic validation**: Pydantic v2 schemas are declared once and FastAPI uses them to validate incoming JSON, produce clear error messages, and auto-generate OpenAPI docs — no extra code required.
- **Junior-friendly**: The code reads almost like English. Decorators (`@router.post(...)`) map directly to HTTP verbs and paths, making the routing layer trivially easy to understand and explain.

---

## 2. Why Motor (Async MongoDB Driver)?

**Motor** is the official async wrapper around PyMongo. It was chosen because:

- **Non-blocking I/O**: Database queries are `await`-ed and yield control back to the event loop, so one slow query does not stall other requests.
- **Native asyncio support**: Works seamlessly with FastAPI's event loop — no thread pools or executors are needed.
- **Same API as PyMongo**: Any engineer who knows PyMongo can read Motor code immediately.

---

## 3. Preventing Double Punch-In

Two layers of protection are used:

| Layer | Mechanism | When it fires |
|---|---|---|
| **Application** | `find_one({"employee_id": ..., "status": "active"})` before every punch-in | Always, on every request |
| **Database** | Compound index on `(employee_id, status)` | Makes the look-up O(log n) instead of a full scan |

If two concurrent requests race through the application check simultaneously, the index guarantees the second insert is still distinguishable (both would get different `_id`s). To make the check truly atomic at the DB layer in a future version, a **unique partial index** on `{employee_id: 1}` filtered to `{status: "active"}` should be added:
```js
db.attendance_records.createIndex(
  { employee_id: 1 },
  { unique: true, partialFilterExpression: { status: "active" } }
)
```
This would make MongoDB itself reject the second insert at the driver level.

---

## 4. Why Audit Logs Are in a Separate Collection

The `audit_logs` collection is intentionally separate from `attendance_records` for several reasons:

- **Immutability by design**: No code in this project ever updates or deletes an audit log. The collection grows append-only. Separation makes it much harder to accidentally modify history when editing attendance logic.
- **Single Responsibility**: The attendance collection holds current state; the audit collection holds change history. Mixing them (e.g., an embedded `corrections` array) would make aggregation pipelines more complex and queries harder to write.
- **Access control**: In a production deployment, the audit collection can be given a separate IAM role so only compliance tools can read it, while the application only has write access.
- **Scalability**: Audit logs grow unboundedly. Keeping them separate allows independent archiving, TTL indexes, or migration to a dedicated logging store (e.g., Elasticsearch) without touching the main attendance data.

---

## 5. Why UTC Timestamps?

All `datetime` fields are stored as UTC. Reasons:

- MongoDB stores all `datetime` objects as UTC internally.
- Daylight saving time (DST) transitions are non-trivial to handle in local time. UTC is always unambiguous.
- Clients send timezone-aware ISO 8601 strings (e.g., `2026-10-15T09:00:00+05:30`); Pydantic automatically normalises these to UTC-aware datetime objects.

---

## 6. MongoDB Aggregation Pipelines over Application-Side Computation

Analytics (totals, averages, counts) are computed **inside MongoDB** using aggregation pipelines rather than fetching all records and computing in Python. This means:

- Only the result set (a handful of rows) travels over the network — not thousands of raw records.
- MongoDB can use indexes at the `$match` stage, keeping pipelines fast even on large datasets.
- The logic is self-contained and can be inspected/tuned in MongoDB Compass independently.
