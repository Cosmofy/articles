import json
import logging

from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from app.observability import JsonFormatter, request_id_context


def format_log(**extra: object) -> dict[str, object]:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    for name, value in extra.items():
        setattr(record, name, value)
    return json.loads(JsonFormatter().format(record))


def test_log_contains_service_node_and_trace_ids() -> None:
    span = NonRecordingSpan(
        SpanContext(
            trace_id=0x1234,
            span_id=0x5678,
            is_remote=False,
            trace_flags=TraceFlags.SAMPLED,
        )
    )
    with trace.use_span(span, end_on_exit=False):
        payload = format_log()

    assert payload["service"] == "articles"
    assert payload["service_namespace"] == "cosmofy"
    assert payload["service_instance_id"]
    assert payload["trace_id"] == "00000000000000000000000000001234"
    assert payload["span_id"] == "0000000000005678"


def test_explicit_request_id_takes_precedence() -> None:
    token = request_id_context.set("context-id")
    try:
        payload = format_log(request_id="record-id")
    finally:
        request_id_context.reset(token)

    assert payload["request_id"] == "record-id"
