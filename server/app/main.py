from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from .core.config import settings
from .core.database import create_db_and_tables
from .routers import crud, functions, upload, media, auth, admin, subscriptions, google_auth
from fastapi.responses import JSONResponse, FileResponse
from fastapi import Request
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI(title=settings.app_name, version="1.0.0")

# CORS - explicit trusted origins only (never "*" with credentials).
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
origins += ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
origins = sorted(set(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; media-src 'self' blob: https:; "
        "frame-src https://www.youtube-nocookie.com https://www.youtube.com; "
        "connect-src 'self' https:; frame-ancestors 'self'"
    )
    if request.url.scheme == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    _migrate_database()
    _seed_admin()
    _seed_settings()
    os.makedirs("uploads", exist_ok=True)
    # Also ensure server/uploads
    os.makedirs(os.path.join(os.path.dirname(__file__), "../../uploads"), exist_ok=True)

def _migrate_database():
    """Add missing columns and tables to databases created previously."""
    try:
        from sqlalchemy import text
        from .core.database import engine
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'user'"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active'"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR DEFAULT 'none'"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_start TIMESTAMP"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expires TIMESTAMP"))
            conn.execute(text("ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS obstacles JSON"))
            conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS lesson_id VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR"))
            conn.execute(text("UPDATE users SET role='user' WHERE role IS NULL"))
            conn.execute(text("UPDATE users SET status='active' WHERE status IS NULL OR status=''"))
            conn.execute(text("UPDATE users SET subscription_status='none' WHERE subscription_status IS NULL"))
    except Exception as e:
        print(f"database migration error: {e}")

def _seed_settings():
    """Seed default settings from environment if not present in DB."""
    try:
        from sqlmodel import Session, select
        from .core.database import engine
        from .models import AdminSetting
        with Session(engine) as session:
            s = session.get(AdminSetting, "default")
            if not s:
                s = AdminSetting(
                    id="default",
                    starter_price=99.0,
                    pro_price=199.0,
                    prime_price=399.0,
                    currency="EGP",
                    groq_api_key=os.getenv("GROQ_API_KEY", "") or settings.groq_api_key,
                    groq_model=os.getenv("GROQ_MODEL", "") or settings.groq_model,
                    gemini_api_key=os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "") or settings.gemini_api_key,
                    gemini_model=os.getenv("GEMINI_MODEL", "") or settings.gemini_model,
                    openai_api_key=os.getenv("OPENAI_API_KEY", "") or settings.openai_api_key,
                    openai_model="gpt-4o-mini",
                    hf_token=os.getenv("HF_TOKEN", "") or settings.hf_token,
                    hf_model=os.getenv("HF_MODEL", "") or settings.hf_model,
                    youtube_api_key=os.getenv("YOUTUBE_API_KEY", "") or settings.youtube_api_key,
                    active_ai_provider="auto",
                )
                session.add(s)
                session.commit()
    except Exception as e:
        print(f"settings seed error: {e}")



def _seed_admin():
    """Create/promote the admin account from ADMIN_EMAIL/ADMIN_PASSWORD env."""
    try:
        from sqlmodel import Session, select
        from .core.database import engine
        from .models import User
        from .core.security import hash_password
        email = (settings.admin_email or "").strip().lower()
        password = settings.admin_password or ""
        if not email or not password:
            return
        with Session(engine) as session:
            user = session.exec(select(User).where(User.email == email)).first()
            if not user:
                user = User(email=email, password_hash=hash_password(password), full_name="ZEUS Admin", role="admin", status="active")
                session.add(user)
            else:
                user.role = "admin"
                user.status = "active"
                user.password_hash = hash_password(password)
                session.add(user)
            session.commit()
            print(f"admin account ready: {email}")
    except Exception as e:
        print(f"admin seed skipped: {e}")


# Health
@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}

@app.get("/api/health")
def api_health():
    return {"status": "ok"}

# Mount uploads static
uploads_path = os.path.join(os.path.dirname(__file__), "../../uploads")
if os.path.exists(uploads_path):
    app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")
else:
    os.makedirs(uploads_path, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

@app.exception_handler(Exception)
async def friendly_handler(request: Request, exc: Exception):
    # Let HTTP exceptions (404 etc.) pass through for SPA fallback
    if isinstance(exc, StarletteHTTPException):
        raise exc
    print(f"Unhandled: {exc}")
    return JSONResponse(status_code=500, content={"reply": "حصل خطأ صغير، جرّب تاني 🙏", "error": "temporary", "retry": True, "toast": "حدث خطأ صغير"})

# Routers: CRUD for all entities
app.include_router(crud.router, prefix="/api/entities", tags=["entities"])
app.include_router(functions.router, prefix="/api/functions", tags=["functions"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(google_auth.router, prefix="/api/auth", tags=["google-auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(subscriptions.router, prefix="/api/subscription", tags=["subscriptions"])
app.include_router(upload.router, prefix="/api", tags=["upload"])

app.include_router(media.router, prefix="/api", tags=["media"])

# Serve Zeus frontend (Vite build) directly on http://127.0.0.1:8000/
DIST_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "dist"))
# Fallback: if running from server/ as cwd with app.main, try ./../dist too
if not os.path.isdir(DIST_DIR):
    alt = os.path.normpath(os.path.join(os.getcwd(), "..", "dist"))
    if os.path.isdir(alt):
        DIST_DIR = alt
if os.path.isdir(DIST_DIR):
    assets_dir = os.path.join(DIST_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_root():
        index = os.path.join(DIST_DIR, "index.html")
        # Never cache the entry HTML: otherwise browsers keep booting a stale
        # JS bundle after each deploy (blank/looping pages).
        return FileResponse(index, headers={"Cache-Control": "no-store"})

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Leave API/docs/health/uploads to their own handlers
        if full_path.startswith(("api/", "docs", "openapi.json", "redoc", "health", "uploads", "assets/")):
            raise StarletteHTTPException(status_code=404, detail="Not found")
        candidate = os.path.normpath(os.path.join(DIST_DIR, full_path))
        # Prevent path traversal + serve real files (favicon, manifest...)
        if candidate.startswith(DIST_DIR) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(DIST_DIR, "index.html"), headers={"Cache-Control": "no-store"})
else:
    print(f"WARNING: frontend dist not found at {DIST_DIR} - only API will be served")
