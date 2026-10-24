from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_auth_endpoints_expose_x_api_key_header_in_swagger():
    schema = app.openapi()

    for path in ["/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/refresh"]:
        params = schema["paths"][path]["post"].get("parameters", [])
        assert any(
            param.get("in") == "header" and param.get("name") == "x-api-key"
            for param in params
        )


def test_preflight_options_requests_are_allowed():
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )

    assert response.status_code in {200, 204}
