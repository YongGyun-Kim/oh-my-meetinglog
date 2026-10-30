from fastapi.testclient import TestClient
from meetinglog.app import create_app


def test_mode_persists_across_app_restarts_and_secret_patch_is_rejected(settings):
    settings.ollama_url = "http://127.0.0.1:1"
    with TestClient(create_app(settings), base_url="http://localhost:8765") as client:
        assert client.patch("/api/settings", json={"mode": "auto"}).status_code == 200
        assert (
            client.patch(
                "/api/settings", json={"mode": "api", "openai_api_key": "should-not-be-accepted"}
            ).status_code
            == 422
        )
    with TestClient(create_app(settings), base_url="http://localhost:8765") as client:
        result = client.get("/api/settings")
        assert result.status_code == 200
        assert result.json()["mode"] == "auto"
        assert "openai_api_key" not in result.text
