"""Local demo HTTP entry point. Serve with one uvicorn worker on loopback."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError

from .commands import BODY_SCHEMA
from .config import Settings
from .errors import APIError
from .inference import Runner
from .media import sanitize
from .service import Service
from .testing.engine_stub import EngineStub


async def bounded_body(request, limit):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise APIError(413, "TOO_LARGE", "Request exceeds the permitted size.")
    return bytes(body)


def bearer(request):
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise APIError(401, "UNAUTHENTICATED", "A valid demo bearer token is required.")
    return token


def strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


async def json_body(request):
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise APIError(415, "UNSUPPORTED_MEDIA", "Use application/json.")
    raw = await bounded_body(request, 16_384)
    try:
        def invalid_number(value):
            raise ValueError("Only integer numbers are allowed")
        result = json.loads(raw, object_pairs_hook=strict_object, parse_float=invalid_number, parse_constant=invalid_number)
        if not isinstance(result, dict):
            raise ValueError("Expected object")
        return result
    except (ValueError, UnicodeError, RecursionError):
        raise APIError(422, "INVALID_REQUEST", "Malformed JSON request.") from None


def create_app(settings=None, engine=None):
    settings = settings or Settings.from_env()
    service = Service(settings)
    runner = Runner(service, engine or EngineStub())

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(service.recover)
        yield
        await runner.close()

    app = FastAPI(title="Mark-1 synthetic backend demo", version="2.0", lifespan=lifespan)
    app.state.service, app.state.runner = service, runner
    app.openapi = service.contracts.bundled_api

    @app.middleware("http")
    async def demo_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Mark1-Mode"] = "synthetic-demo-only"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(APIError)
    async def api_error(request, exc):
        return JSONResponse(exc.payload, status_code=exc.status)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        error = APIError(exc.status_code, "HTTP_ERROR", "The requested operation is unavailable.")
        return JSONResponse(error.payload, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def request_error(request, exc):
        error = APIError(422, "INVALID_REQUEST", "Request does not match the published contract.")
        return JSONResponse(error.payload, status_code=422)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, exc):
        error = APIError(503, "STORAGE_UNAVAILABLE", "Storage is unavailable; reconcile the original command before retrying.")
        return JSONResponse(error.payload, status_code=503)

    @app.exception_handler(ValueError)
    async def invalid_internal(request, exc):
        error = APIError(503, "INTERNAL_VALIDATION_FAILURE", "Required state could not be validated.")
        return JSONResponse(error.payload, status_code=503)

    @app.get("/health")
    async def health():
        return {"mode": "synthetic-demo-only", "contract_version": "2.0", "engine": "injected" if engine else "deterministic-stub"}

    @app.get("/v2/sessions/{session_id}")
    async def read_session(session_id: str, request: Request):
        return await asyncio.to_thread(service.read, bearer(request), session_id)

    @app.get("/v2/sessions/{session_id}/events")
    async def events(session_id: str, request: Request, cursor: str | None = None):
        return await asyncio.to_thread(service.events, bearer(request), session_id, cursor)

    @app.get("/v2/sessions/{session_id}/commands/{command_id}")
    async def receipt(session_id: str, command_id: str, request: Request):
        return await asyncio.to_thread(service.receipt, bearer(request), session_id, command_id)

    async def command(request, operation, session_id=None):
        token = bearer(request)
        # Authenticate before parsing user data; field IDs never set caller identity.
        with service.store.connect() as db:
            service.store.authenticate(db, token)
        data = await json_body(request)
        result, status, headers, sid = await asyncio.to_thread(service.perform, token, operation, session_id,
                                                              request.headers.get("idempotency-key"), data)
        if result.get("status") == "EVALUATING":
            runner.schedule(token, sid)
        return JSONResponse(result, status_code=status, headers=headers)

    @app.post("/v2/sessions")
    async def create(request: Request):
        return await command(request, "create")

    @app.post("/v2/sessions/{session_id}/images")
    async def upload(session_id: str, request: Request):
        token = bearer(request)
        with service.store.connect() as db:
            principal = service.store.authenticate(db, token)
            service.store.session(db, session_id, principal)
        if not request.headers.get("content-type", "").startswith("multipart/form-data;"):
            raise APIError(415, "UNSUPPORTED_MEDIA", "Use multipart/form-data.")
        raw = await bounded_body(request, settings.max_image_bytes + 65_536)
        delivered = False

        async def receive():
            nonlocal delivered
            body = b"" if delivered else raw
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        try:
            async with Request(request.scope, receive=receive).form(max_files=1, max_fields=2, max_part_size=settings.max_image_bytes) as form:
                if set(form) != {"file", "expected_revision", "purpose"} or len(form.multi_items()) != 3:
                    raise ValueError("Unexpected multipart fields")
                file = form["file"]
                if (not isinstance(file, UploadFile) or not isinstance(form["expected_revision"], str)
                        or not form["expected_revision"].isdigit() or not isinstance(form["purpose"], str)
                        or form["purpose"] not in ("identity", "investigation", "observation")):
                    raise ValueError("Invalid file or revision")
                image = await file.read(settings.max_image_bytes + 1)
                data = {"expected_revision": int(form["expected_revision"]), "purpose": form["purpose"],
                        "raw_sha256": hashlib.sha256(image).hexdigest()}
                media = await asyncio.to_thread(sanitize, image, file.content_type, settings)
        except APIError:
            raise
        except Exception:
            raise APIError(422, "INVALID_REQUEST", "Invalid multipart image request.") from None
        result, status, headers, _ = await asyncio.to_thread(service.perform, token, "images", session_id,
                                                            request.headers.get("idempotency-key"), data, media)
        return JSONResponse(result, status_code=status, headers=headers)

    @app.post("/v2/sessions/{session_id}/{operation}")
    async def mutate(session_id: str, operation: str, request: Request):
        if operation not in BODY_SCHEMA or operation == "create":
            raise APIError(404, "NOT_FOUND", "Operation is unavailable.")
        return await command(request, operation, session_id)

    return app
