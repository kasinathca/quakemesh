import json

from aws.lambdas.common import failure, success


def test_aws_v2_success_envelope_and_request_header():
    response = success("request-1", {"status": "ok"})
    assert response["statusCode"] == 200
    assert response["headers"]["X-Request-ID"] == "request-1"
    assert json.loads(response["body"]) == {
        "schema_version": "2.0",
        "request_id": "request-1",
        "data": {"status": "ok"},
    }


def test_aws_v2_error_envelope_preserves_details():
    response = failure("request-2", 409, "EXAMPLE", "Conflict.", {"field": "value"})
    body = json.loads(response["body"])
    assert response["statusCode"] == 409
    assert body["schema_version"] == "2.0"
    assert body["error"] == {
        "code": "EXAMPLE",
        "message": "Conflict.",
        "request_id": "request-2",
        "details": {"field": "value"},
    }
