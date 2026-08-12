"""FastAPI server for Studio — thin routes over StudioService, plus an SSE job stream. Imports
fastapi (studio extra); never imported by the core CLI unless `robotbase studio` runs."""
from __future__ import annotations

import asyncio
import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from robotbase.studio.service import StudioService

_HERE = os.path.dirname(__file__)


def create_app(project_dir: str, service: StudioService | None = None) -> FastAPI:
    app = FastAPI(title="Robotbase Studio")
    svc = service or StudioService(project_dir)
    os.makedirs(os.path.join(_HERE, "static"), exist_ok=True)      # exists before Task 5 fills it
    os.makedirs(os.path.join(_HERE, "templates"), exist_ok=True)
    templates = Jinja2Templates(directory=os.path.join(_HERE, "templates"))
    app.mount("/static", StaticFiles(directory=os.path.join(_HERE, "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(request, "index.html", {"project": svc.project()})

    @app.get("/api/project")
    def api_project():
        return svc.project()

    @app.get("/api/runs")
    def api_runs():
        return svc.list_runs()

    @app.get("/api/runs/{run_id}")
    def api_run(run_id: str):
        return svc.get_run(run_id)

    @app.delete("/api/runs")
    def api_clear_runs():
        return svc.clear_runs()

    @app.delete("/api/runs/{run_id}")
    def api_delete_run(run_id: str):
        try:
            return svc.delete_run(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/evals")
    def api_evals():
        return svc.list_evals()

    @app.get("/api/evals/{eval_id}")
    def api_eval(eval_id: str):
        return svc.get_eval(eval_id)

    @app.delete("/api/evals")
    def api_clear_evals():
        return svc.clear_evals()

    @app.delete("/api/evals/{eval_id}")
    def api_delete_eval(eval_id: str):
        try:
            return svc.delete_eval(eval_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/job/stop")
    def api_job_stop():
        return svc.stop_job()

    @app.get("/api/files")
    def api_files():
        return svc.list_files()

    @app.get("/api/files/content")
    def api_file_content(path: str):
        try:
            return svc.read_file(path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="file not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/files/save")
    async def api_file_save(request: Request):
        body = await request.json()
        try:
            return svc.write_file(body.get("path"), body.get("content"))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="file not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))


    @app.get("/api/status")
    def api_status():
        return svc.status()

    @app.post("/api/telemetry/ensure")
    def api_telemetry_ensure():
        # Called when the 3D viewer opens, so live motion works for a sim the agent launched.
        return svc.ensure_telemetry()

    @app.get("/api/foxglove-url")
    def api_foxglove():
        return svc.foxglove()

    @app.get("/api/job")
    def api_job():
        return svc.job_snapshot()

    @app.post("/api/up")
    def api_up():
        return _job_dict(svc.start_up())

    @app.post("/api/down")
    def api_down():
        return _job_dict(svc.start_down())

    @app.post("/api/run")
    async def api_run_start(request: Request):
        body = await request.json()
        return _job_dict(svc.start_run(body["scenario"]))

    @app.post("/api/eval")
    async def api_eval_start(request: Request):
        b = await request.json()
        return _job_dict(svc.start_eval(b.get("scenario"), int(b.get("trials", 10)),
                                        int(b.get("seed", 0)), bool(b.get("all", False))))

    @app.get("/events")
    async def events():
        async def gen():
            while True:
                snap = svc.job_snapshot()
                yield f"data: {json.dumps(snap)}\n\n"
                await asyncio.sleep(1.0 if snap.get("status") != "running" else 0.5)
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/telemetry")
    async def telemetry():
        async def gen():
            while True:
                yield f"data: {json.dumps(svc.latest_pose())}\n\n"
                await asyncio.sleep(0.1)
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


def _job_dict(job) -> dict:
    return {"id": job.id, "kind": job.kind, "label": job.label,
            "status": job.status, "error": job.error}


def run_server(project_dir: str, port: int = 8080, open_browser: bool = True) -> None:
    # Source specs are authoritative. Reconcile generated URDF/SDF before the first page render.
    from robotbase.generator import recompile_project
    recompile_project(project_dir)
    import uvicorn
    if open_browser:
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print(f"Robotbase Studio → http://127.0.0.1:{port}  (Ctrl-C to stop)")
    uvicorn.run(create_app(project_dir), host="127.0.0.1", port=port, log_level="warning")
