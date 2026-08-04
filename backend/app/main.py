from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.util import get_remote_address
from backend.app.api.routes import router
from backend.app.core.config import get_settings
from backend.app.db.session import Base, engine

settings = get_settings()
Base.metadata.create_all(bind=engine)
app = FastAPI(title="ShopSense API", version="1.0.0")
app.state.limiter = Limiter(key_func=get_remote_address)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
Instrumentator().instrument(app).expose(app)


@app.get("/health")
def health():
    return {"status": "ok"}
