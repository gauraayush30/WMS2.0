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
from routes.legacy import router as legacy_router


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
app.include_router(legacy_router)
