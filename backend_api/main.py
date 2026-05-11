print("THIS FILE IS RUNNING")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import migrations
from scheduler import create_scheduler

# ── Route modules ────────────────────────────────────────────────────────────
from routes.auth import router as auth_router
from routes.business import router as business_router
from routes.products import router as products_router
from routes.inventory import router as inventory_router
from routes.users import router as users_router
from routes.invites import router as invites_router
from routes.delivery_locations import router as delivery_locations_router
from routes.dashboard import router as dashboard_router
from routes.legacy import router as legacy_router
from routes.ml_proxy import router as ml_proxy_router
from routes.ml_portfolio import router as ml_portfolio_router
from routes.reports import router as reports_router
from routes.location_utilization import router as location_utilization_router
from routes.warehouses import router as warehouses_router
from routes.customers import router as customers_router
from routes.inbounds import router as inbounds_router
from routes.outbounds import router as outbounds_router
from routes.analytics import router as analytics_router
from routes.buyers import router as buyers_router
from routes.sellers import router as sellers_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks (migrations) before the app begins serving requests."""
    migrations.run_all()
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(business_router)
app.include_router(products_router)
app.include_router(inventory_router)
app.include_router(users_router)
app.include_router(invites_router)
app.include_router(delivery_locations_router)
app.include_router(dashboard_router)
app.include_router(legacy_router)
app.include_router(ml_proxy_router)
app.include_router(ml_portfolio_router)
app.include_router(reports_router)
app.include_router(location_utilization_router)
app.include_router(warehouses_router)
app.include_router(customers_router)
app.include_router(inbounds_router)
app.include_router(outbounds_router)
app.include_router(analytics_router)
app.include_router(buyers_router)
app.include_router(sellers_router)
