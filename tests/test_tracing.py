from unittest.mock import Mock

from app.telemetry import _redact_server_query


def test_server_trace_redacts_query_values() -> None:
    span = Mock()
    span.is_recording.return_value = True

    _redact_server_query(
        span,
        {
            "path": "/articles",
            "scheme": "https",
            "headers": [(b"host", b"articles.example.com")],
            "query_string": b"search=private",
        },
    )

    attributes = dict(call.args for call in span.set_attribute.call_args_list)
    assert attributes["http.target"] == "/articles"
    assert attributes["url.full"] == "https://articles.example.com/articles"
    assert attributes["url.query"] == "[REDACTED]"
