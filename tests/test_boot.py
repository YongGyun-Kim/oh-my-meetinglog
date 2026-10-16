def test_boot_creates_persistent_store(tmp_path):
    from fastapi.testclient import TestClient
    from meetinglog.app import create_app
    from meetinglog.config import Settings

    for _ in range(2):
        with TestClient(
            create_app(Settings(data_dir=tmp_path)), base_url="http://localhost:8765"
        ) as client:
            assert client.get("/api/health").json() == {"status": "ok"}
    assert (tmp_path / "meetinglog.sqlite3").is_file()


def test_external_host_and_origin_are_rejected(tmp_path):
    from fastapi.testclient import TestClient
    from meetinglog.app import create_app
    from meetinglog.config import Settings

    with TestClient(
        create_app(Settings(data_dir=tmp_path)), base_url="http://localhost:8765"
    ) as client:
        assert client.get("/api/health", headers={"host": "attacker.example"}).status_code == 400
        assert (
            client.post(
                "/api/recordings", headers={"origin": "https://attacker.example"}
            ).status_code
            == 403
        )
