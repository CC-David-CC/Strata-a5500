"""Optional educational UI. Strata remains the only inference service."""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .catalog import BY_ID, PAGES
from .client import Backend, Context, RECORDINGS
from .core import validate_groups
from .scenarios import run_page, speculation_receipts

STATIC = Path(__file__).with_name('static')


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Choice(StrictModel):
    label: str = Field(pattern=r'^[A-P]$')
    description: str = Field(min_length=1, max_length=500)
    value: float | None = None


class Group(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    answers: list[str] = Field(min_length=1, max_length=4)


class Source(StrictModel):
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=3000)


class Run(StrictModel):
    mode: Literal['recorded', 'live'] = 'recorded'
    state: str | None = Field(default=None, min_length=1, max_length=3000)
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    strategy: Literal['fast', 'complete'] | None = None
    choices: list[Choice] | None = Field(default=None, min_length=2, max_length=8)
    groups: list[Group] | None = Field(default=None, min_length=2, max_length=4)
    sources: list[Source] | None = Field(default=None, min_length=1, max_length=6)
    controller_state: Literal['unread', 'inspected', 'edited', 'verified', 'done'] | None = None
    threshold: float | None = Field(default=None, ge=0, le=1)
    parallel: int | None = Field(default=None, ge=1, le=4)
    repeats: int | None = Field(default=None, ge=1, le=5)
    case: Literal['decision', 'router', 'ambiguity', 'stream', 'grammar', 'json-schema',
                  'reasoning-json', 'tool-call', 'tool-result', 'selected-only'] | None = None

    @model_validator(mode='after')
    def unique(self):
        if self.choices and len({c.label for c in self.choices}) != len(self.choices):
            raise ValueError('Answer labels must be unique')
        if self.sources and len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError('Source IDs must be unique')
        if self.groups:
            validate_groups([g.model_dump() for g in self.groups])
        return self


def create_app(backend_factory=None):
    app = FastAPI(title='Strata Control Lab', docs_url='/api/docs', redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]'])
    app.state.active_runs = 0
    make_backend = backend_factory or (lambda mode: Backend(mode))

    @app.middleware('http')
    async def local_boundary(request, call_next):
        if request.method == 'POST':
            origin = request.headers.get('origin')
            if request.headers.get('x-control-lab') != '1':
                return JSONResponse({'detail': 'Use the local Control Lab client header'}, status_code=403)
            if origin and urlsplit(origin).netloc != request.headers.get('host'):
                return JSONResponse({'detail': 'Cross-origin control requests are not allowed'}, status_code=403)
            length = request.headers.get('content-length', '0')
            if not length.isdigit() or int(length) > 40000:
                return JSONResponse({'detail': 'Request exceeds 40 KB'}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.get('/api/catalog')
    async def catalog():
        return {'pages': PAGES, 'recordings': len(list(RECORDINGS.glob('*.json'))),
                'base_commit': '2243cb1c5b1a87270731d8b8a76e4af001f96f97',
                'live_backend_configured_on_server': True}

    @app.get('/api/evidence/speculation')
    async def evidence():
        return speculation_receipts()

    @app.post('/api/run/{name}')
    async def run(name: str, body: Run):
        if name not in BY_ID:
            raise HTTPException(404, 'Unknown experiment')
        overrides = body.model_dump(exclude_none=True, exclude={'mode'})
        unknown = overrides.keys() - BY_ID[name]['defaults'].keys()
        if unknown:
            raise HTTPException(422, 'This experiment does not use: ' + ', '.join(sorted(unknown)))
        if name == 'graph' and body.threshold is not None and not 0 < body.threshold < 1:
            raise HTTPException(422, 'Graph threshold must be inside (0, 1)')
        if name == 'score' and body.choices and any(c.value is None for c in body.choices):
            raise HTTPException(422, 'Every score level needs an explicit numeric value')
        if app.state.active_runs >= 2:
            raise HTTPException(429, 'Two lab runs are active. Stop one before starting another.')

        async def events():
            queue = asyncio.Queue(maxsize=128)
            async def emit(kind, data):
                await queue.put({'type': kind, **data})

            async def work():
                try:
                    async with make_backend(body.mode) as backend:
                        ctx = Context(backend, emit)
                        start = time.perf_counter()
                        result = await run_page(ctx, name, overrides)
                        await emit('result', {'result': result, 'receipt': ctx.receipt(),
                                              'wall_ms': (time.perf_counter() - start) * 1000})
                except asyncio.CancelledError:
                    raise
                except (ValueError, KeyError, OSError, RuntimeError) as exc:
                    await emit('error', {'message': str(exc)})
                except Exception as exc:
                    # httpx errors and unexpected faults are reported as failure, never success.
                    await emit('error', {'message': f'{type(exc).__name__}: {exc}'})
                await queue.put(None)

            app.state.active_runs += 1
            task = asyncio.create_task(work())
            try:
                yield 'data: ' + json.dumps({'type': 'started', 'mode': body.mode}) + '\n\n'
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield 'data: ' + json.dumps(item, ensure_ascii=False, allow_nan=False) + '\n\n'
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                app.state.active_runs -= 1

        return StreamingResponse(events(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    app.mount('/static', StaticFiles(directory=STATIC), name='static')

    @app.get('/')
    @app.get('/lab/{name}')
    async def index(name: str = 'choice'):
        if name not in BY_ID:
            raise HTTPException(404, 'Unknown experiment')
        return FileResponse(STATIC / 'index.html')

    return app
