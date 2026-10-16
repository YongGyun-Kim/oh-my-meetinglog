from tests.api_fixtures import populated_client


def test_exports_exclude_secrets_paths_and_keep_edited_text(settings, db, tmp_path, caplog):
    client, record_id, transcript = populated_client(settings, db, tmp_path)
    try:
        edited = client.patch(
            f"/api/recordings/{record_id}/transcript",
            json={
                "base_version_id": transcript.id,
                "changes": [{"turn_id": "t2", "text": "이번 주에 시작합니다."}],
            },
        ).json()
        response = client.get(f"/api/recordings/{record_id}/export?format=json")
        assert response.status_code == 200
        payload = response.json()
        assert payload["schema_version"] == 1
        assert payload["transcript"]["id"] == edited["id"]
        assert payload["transcript"]["turns"][1]["text_original"] == "다음 주에 시작하겠습니다."
        assert payload["transcript"]["turns"][1]["text_edited"] == "이번 주에 시작합니다."
        markdown = client.get(f"/api/recordings/{record_id}/export?format=markdown")
        assert markdown.status_code == 200
        assert "이번 주에 시작합니다." in markdown.text
        settings_response = client.get("/api/settings")
        for text in [response.text, markdown.text, settings_response.text, caplog.text]:
            assert "canary-secret-never-expose" not in text
            assert str(settings.data_dir) not in text
            assert "raw_artifact" not in text
    finally:
        client.__exit__(None, None, None)
