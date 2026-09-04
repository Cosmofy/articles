import os
from socket import gethostname

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def _redact_server_query(span, scope: dict[str, object]) -> None:
    if not span.is_recording():
        return

    path = str(scope.get("path", ""))
    scheme = str(scope.get("scheme", "http"))
    headers = dict(scope.get("headers", []))
    host = headers.get(b"host", b"")
    host = host.decode("latin-1") if isinstance(host, bytes) else str(host)
    safe_url = f"{scheme}://{host}{path}" if host else path
    span.set_attribute("http.target", path)
    span.set_attribute("http.url", safe_url)
    span.set_attribute("url.full", safe_url)
    span.set_attribute("url.query", "[REDACTED]")


def configure_telemetry(app: FastAPI) -> TracerProvider:
    # OTEL_NODE_NAME should be articles-node-a or articles-node-b in production. The host
    # name is a safe non-null fallback for local development and other environments.
    node_name = os.getenv("OTEL_NODE_NAME", "").strip() or gethostname()

    deployment_environment = os.getenv("DEPLOYMENT_ENVIRONMENT", "development")

    resource = Resource.create(
        {
            "service.name": "articles",
            "service.namespace": "cosmofy",
            "service.version": app.version,
            "service.instance.id": node_name,
            "host.name": node_name,
            "deployment.environment.name": deployment_environment,
            "cloud.provider": "oracle_cloud",
        }
    )

    provider = TracerProvider(resource=resource)

    # The endpoint is intentionally fixed to the private collector on loopback.
    # The application contains no AWS exporter or credentials; only the colocated
    # collector may forward traces to AWS X-Ray.
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint="http://127.0.0.1:24318/v1/traces")
        )
    )

    trace.set_tracer_provider(provider)

    # Continue the W3C trace context received from the Java GraphQL service.
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        server_request_hook=_redact_server_query,
    )

    # Trace Redis cache and rate-limit commands.
    RedisInstrumentor().instrument(tracer_provider=provider)

    return provider
