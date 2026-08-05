from fastapi.testclient import TestClient


def test_health_returns_http_200(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200


def test_health_response_schema(client: TestClient) -> None:
    response = client.get("/health")

    assert response.json() == {"status": "ok"}


def test_ready_returns_http_200(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"configuration": "ok"},
    }


def test_request_id_is_preserved(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req-test-001"})

    assert response.headers["X-Request-ID"] == "req-test-001"

