# ============================================================
# main.py
# ------------------------------------------------------------
# The entry point of the backend.
#
# Run with:   uvicorn app.main:app --reload
#
# Then open:
#   http://127.0.0.1:8000          -> basic welcome
#   http://127.0.0.1:8000/docs     -> interactive API docs
#   http://127.0.0.1:8000/health   -> health check
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth as auth_router
from app.routers import properties as properties_router
from app.routers import users as users_router
from app.routers import leases as leases_router
from app.routers import payments as payments_router
from app.routers import work_orders as work_orders_router
from app.routers import password_reset as password_reset_router
from app.routers import org_email as org_email_router
from app.routers import uploads as uploads_router
from app.routers import taxes as taxes_router
from app.routers import utilities as utilities_router
from app.routers import insurance as insurance_router
from app.routers import expenses as expenses_router
from app.routers import tenant_insurance as tenant_insurance_router

# ------------------------------------------------------------
# Create the FastAPI app
# ------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Property Management Platform API",
)


# ------------------------------------------------------------
# CORS
# ------------------------------------------------------------
# Lets the frontend (Next.js) talk to this backend.
# During development we allow common localhost ports.
# We'll tighten this up before going to production.
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Register routers
# ------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(properties_router.router)
app.include_router(users_router.router)
app.include_router(leases_router.router)
app.include_router(payments_router.router)
app.include_router(work_orders_router.router)
app.include_router(password_reset_router.router)
app.include_router(org_email_router.router)
app.include_router(uploads_router.router)
app.include_router(taxes_router.router)
app.include_router(utilities_router.router)
app.include_router(insurance_router.router)
app.include_router(expenses_router.router)
app.include_router(tenant_insurance_router.router)



# ------------------------------------------------------------
# Root + health check
# ------------------------------------------------------------
@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}