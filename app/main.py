import os
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

app = FastAPI(title="Task API", version="1.0.0")
REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"] )
LATENCY = Histogram("http_request_duration_seconds", "HTTP request duration", ["method", "path"] ) 

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    priority: Literal["low", "medium", "high"] = "medium"   

class Task(TaskCreate):
    id: int
    completed: bool = False

class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    priority: Literal["low", "medium", "high"] | None = None
    completed: bool | None = None

tasks: dict[int, Task] = {}
next_id = 1

@app.middleware("http")
async def observe_request(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    return response

@app.get("/health/live")
def live(): return {"status": "ok"}

@app.get("/health/ready")
def ready(): return {"status": "ok"}

@app.get("/version")
def version():
    return {"service": "task-api", "version": "1.0.0",
            "git_commit": os.getenv("GIT_COMMIT", "local"),
            "build_time": os.getenv("BUILD_TIME", "local")}

@app.get("/metrics", include_in_schema=False)
def metrics(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/tasks", response_model=Task, status_code=201)
def create_task(data: TaskCreate):
    global next_id
    task = Task(id=next_id, **data.model_dump())
    tasks[next_id] = task
    next_id += 1
    return task 

@app.get("/tasks", response_model=list[Task])
def list_tasks(): return list(tasks.values())

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    if task_id not in tasks: raise HTTPException(404, "Task not found")
    return tasks[task_id]

@app.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, data: TaskUpdate):
    if task_id not in tasks: raise HTTPException(404, "Task not found")
    updated = tasks[task_id].model_copy(update=data.model_dump(exclude_none=True))
    tasks[task_id] = updated
    return updated    

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    if task_id not in tasks: raise HTTPException(404, "Task not found")
    del tasks[task_id]
    return Response(status_code=204)