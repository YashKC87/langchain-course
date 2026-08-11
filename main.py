"""Compatibility entry — prefer `cd backend && uvicorn app.main:app`."""

print(
    "Agent Metering & Observability Control Center\n"
    "Start backend:  cd backend && uvicorn app.main:app --reload --port 8000\n"
    "Start frontend: cd frontend && npm run dev\n"
)
