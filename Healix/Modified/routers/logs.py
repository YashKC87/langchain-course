# ============================================================
#  HEALIX Logs Router — routers/logs.py
# ============================================================

from fastapi import APIRouter, Request, Query
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import LogIngestRequest, SyslogIngestRequest, LogQueryRequest

router = APIRouter(prefix="/api/logs", tags=["Log Management"])


@router.get("")
async def query_logs(request: Request, source: Optional[str] = None,
                     severity: Optional[str] = None, search: Optional[str] = None,
                     hours: int = Query(24, le=720), limit: int = Query(200, le=1000),
                     offset: int = 0):
    logs = await request.app.state.db.query_logs(
        source=source, severity=severity, search=search,
        hours=hours, limit=limit, offset=offset
    )
    return {"logs": logs, "count": len(logs)}


@router.get("/stats")
async def log_stats(request: Request, hours: int = Query(24, le=720)):
    return await request.app.state.db.get_log_stats(hours=hours)


@router.get("/sources")
async def log_sources(request: Request):
    return {"sources": await request.app.state.db.get_log_sources()}


@router.post("/ingest")
async def ingest_logs(request: Request, body: LogIngestRequest):
    entries = [e.model_dump() for e in body.entries]
    count = await request.app.state.log_pipeline.ingest_custom_log(body.source, entries)
    return {"ingested": count, "source": body.source}


@router.post("/syslog")
async def ingest_syslog(request: Request, body: SyslogIngestRequest):
    count = await request.app.state.log_pipeline.ingest_syslog_raw(body.raw)
    return {"ingested": count}


@router.post("/query")
async def advanced_query(request: Request, body: LogQueryRequest):
    logs = await request.app.state.db.query_logs(
        search=body.query, hours=body.hours, limit=body.limit
    )
    return {"logs": logs, "count": len(logs), "query": body.query}
