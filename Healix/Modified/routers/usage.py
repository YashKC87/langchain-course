# ============================================================
#  HEALIX Usage Router — routers/usage.py
# ============================================================

from fastapi import APIRouter, Request, Query

router = APIRouter(prefix="/api/usage", tags=["Usage Analytics"])


@router.get("/summary")
async def usage_summary(request: Request, period: str = Query("7d")):
    return await request.app.state.usage_analytics.get_usage_summary(period=period)


@router.get("/adoption")
async def adoption_metrics(request: Request):
    return await request.app.state.usage_analytics.get_adoption_metrics()


@router.get("/workload")
async def workload_distribution(request: Request):
    return await request.app.state.usage_analytics.get_workload_distribution()


@router.get("/tokens")
async def token_usage(request: Request, period: str = Query("30d")):
    return await request.app.state.usage_analytics.get_token_usage(period=period)


@router.get("/efficiency")
async def efficiency_metrics(request: Request):
    return await request.app.state.usage_analytics.get_efficiency_metrics()
