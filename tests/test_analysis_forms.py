import sys

import pytest
from meetinglog.domain import AnalysisVersion, new_id
from meetinglog.jobs.repository import JobRepository
from meetinglog.jobs.runner import Worker

from tests.analysis_fixtures import form_analysis_fixture
from tests.api_fixtures import populated_client


@pytest.mark.parametrize("form", ["meeting", "project", "decision", "progress", "interview"])
def test_selected_form_survives_queue_worker_and_publication(settings, db, tmp_path, form):
    client, record_id, transcript = populated_client(settings, db, tmp_path)
    try:
        assert {option["id"] for option in client.get("/api/recordings/analysis-forms").json()} == {
            "meeting",
            "interview",
            "project",
            "decision",
            "progress",
        }
        endpoint = f"/api/recordings/{record_id}/analyze"
        other = "project" if form == "meeting" else "meeting"
        payload = {"mode": "local_only", "transcript_id": transcript.id, "form": form}
        first = client.post(endpoint, json=payload)
        assert first.status_code == 200
        assert first.json()["form"] == form
        assert client.post(endpoint, json=payload).json()["id"] == first.json()["id"]
        assert client.post(endpoint, json={**payload, "form": other}).status_code == 409
        assert client.post(endpoint, json={**payload, "form": "unknown"}).status_code == 422

        def command(request):
            assert request.form == form
            version = AnalysisVersion(
                id=new_id(),
                transcript_id=transcript.id,
                body=form_analysis_fixture(form),
                provider="test",
                model="fixed",
                prompt_version="3",
                form=request.form,
            )
            return [
                sys.executable,
                "-c",
                "from pathlib import Path;import sys;Path(sys.argv[1]).write_text(sys.argv[2])",
                request.output_path,
                version.model_dump_json(),
            ]

        with Worker(settings, db, stage_command=command) as worker:
            worker.run_once()
        assert JobRepository(db).get(first.json()["id"]).state == "succeeded"
        detail = client.get(f"/api/recordings/{record_id}").json()
        assert detail["analysis"]["form"] == form
        exported = client.get(f"/api/recordings/{record_id}/export?format=json").json()
        assert exported["schema_version"] == 3
        assert exported["analysis"]["form"] == form
        second = client.post(endpoint, json={**payload, "form": other})
        assert second.status_code == 200
        assert second.json()["id"] != first.json()["id"]
        assert second.json()["form"] == other
    finally:
        client.__exit__(None, None, None)
