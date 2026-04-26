"""OpenTelemetry tracing — single trace ID propagated across A2A.

`init_tracing(service_name)` is called once per service at import time. It
configures a TracerProvider that exports spans to Cloud Trace and tags them
with GCP resource attributes (project, Cloud Run revision, etc.).

`install_fastapi_middleware(app, service_name)` adds an ASGI middleware that
extracts W3C traceparent from inbound requests so each peer's spans share
a single trace ID with the originating Listing Service request.

`traced_a2a_span(audience)` (used in shared.a2a) creates the outbound span
and returns the headers dict to inject into httpx so the receiving FastAPI
middleware picks up the same trace.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from opentelemetry import propagate, trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.resourcedetector.gcp_resource_detector import (
    GoogleCloudResourceDetector,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)

logger = logging.getLogger("surplusas.tracing")

_initialized = False


def init_tracing(service_name: str) -> None:
    """Idempotent: configure the global tracer provider and propagator."""
    global _initialized
    if _initialized:
        return

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")

    base = Resource.create({"service.name": service_name})
    try:
        gcp = GoogleCloudResourceDetector(raise_on_error=False).detect()
        resource = base.merge(gcp)
    except Exception:
        logger.debug("GCP resource detection skipped (likely local dev).")
        resource = base

    provider = TracerProvider(resource=resource)
    if project:
        try:
            exporter = CloudTraceSpanExporter(project_id=project)
            # SimpleSpanProcessor flushes synchronously per span. On Cloud Run,
            # BatchSpanProcessor's daemon thread can be paused when instances
            # idle, causing spans to be dropped on the floor.
            provider.add_span_processor(SimpleSpanProcessor(exporter))
        except Exception as e:
            logger.warning("CloudTraceSpanExporter init failed: %s", e)
    trace.set_tracer_provider(provider)

    propagate.set_global_textmap(
        CompositePropagator([TraceContextTextMapPropagator()])
    )

    _initialized = True
    logger.info("Tracing initialized for service=%s project=%s", service_name, project)


def install_fastapi_middleware(app, service_name: str) -> None:
    """Add a middleware that creates a server span per request and adopts
    any inbound W3C traceparent so peer services share the same trace ID.
    """
    tracer = trace.get_tracer(service_name)

    @app.middleware("http")
    async def _trace_middleware(request, call_next):
        ctx = propagate.extract(dict(request.headers))
        span_name = f"{request.method} {request.url.path}"
        with tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=trace.SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.target": request.url.path,
                "service.name": service_name,
            },
        ) as span:
            try:
                response = await call_next(request)
            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
            span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
            return response


@contextmanager
def a2a_client_span(audience: str, headers: dict) -> Iterator[dict]:
    """Wrap an outbound A2A call in a CLIENT span and inject traceparent.

    Mutates `headers` in place to add `traceparent` (and any other registered
    propagation keys) so the receiving FastAPI middleware can attach to this
    same trace.
    """
    tracer = trace.get_tracer("surplusas.a2a")
    with tracer.start_as_current_span(
        f"a2a.call_peer",
        kind=trace.SpanKind.CLIENT,
        attributes={
            "peer.url": audience,
            "rpc.system": "a2a",
        },
    ) as span:
        propagate.inject(headers)
        try:
            yield headers
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise
