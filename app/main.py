from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routers import admin, regulations, tree

app = FastAPI(title="아신대학교 규정정보시스템")

app.include_router(tree.router, prefix="/api")
app.include_router(regulations.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache"
    return response


static_dir = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
