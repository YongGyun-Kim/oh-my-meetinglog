import pytest
from meetinglog.domain import Action, AnalysisVersion, Fact, Recording
from meetinglog.exports import Exporter

from tests.analysis_fixtures import analysis_fixture, transcript_fixture
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
        assert payload["schema_version"] == 2
        assert payload["transcript"]["id"] == edited["id"]
        assert (
            payload["transcript"]["turns"][1]["sentences"][0]["text_original"]
            == "다음 주에 시작하겠습니다."
        )
        assert (
            payload["transcript"]["turns"][1]["sentences"][0]["text_edited"]
            == "이번 주에 시작합니다."
        )
        markdown = client.get(f"/api/recordings/{record_id}/export?format=markdown")
        assert markdown.status_code == 200
        assert "이번 주에 시작합니다." in markdown.text
        assert "다음 주에 시작하겠습니다." in markdown.text
        assert edited["id"] in markdown.text
        assert f"기록 ID: {record_id}" in markdown.text
        settings_response = client.get("/api/settings")
        for text in [response.text, markdown.text, settings_response.text, caplog.text]:
            assert "canary-secret-never-expose" not in text
            assert str(settings.data_dir) not in text
            assert "raw_artifact" not in text
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize("with_analysis", [True, False])
def test_markdown_handoff_keeps_evidence_versions_and_review_context(with_analysis):
    recording = Recording(id="recording", title="기획 회의", source="file", input_state="ready")
    transcript = transcript_fixture(recording.id)
    transcript.speakers[1].role = "개발 담당"
    transcript.turns[1].sentences[0].text_edited = "18일에 초안을 공유하겠습니다."
    transcript.turns[1].sentences[0].review_flags = ["alignment_uncertain", "overlap"]
    body = analysis_fixture()
    body.agreements = [Fact(text="초안을 공유한다.", evidence_sentence_ids=["t2"])]
    body.open_questions = [Fact(text="공유 시간을 정해야 한다.", evidence_sentence_ids=["t2"])]
    body.actions = [
        Action(
            text="초안 공유",
            owner_speaker_id="b",
            due_text="18일",
            evidence_sentence_ids=["t2"],
        )
    ]
    analysis = AnalysisVersion(
        id="analysis-1",
        transcript_id=transcript.id,
        body=body,
        provider="test",
        model="fixed",
        prompt_version="1",
    )
    markdown = Exporter.markdown(
        {
            "recording": recording.model_dump(mode="json"),
            "transcript": transcript.model_dump(mode="json"),
            "analysis": analysis.model_dump(mode="json") if with_analysis else None,
        }
    )

    assert "기록 ID: recording" in markdown
    assert "전사 버전: version-1" in markdown
    assert "녹음 시각:" not in markdown
    assert "개발 담당" in markdown
    assert "#### t1" in markdown
    turn = markdown.split("#### t2", 1)[1]
    assert "00:00:02.200" in turn
    assert "00:00:05.000" in turn
    assert "18일에 초안을 공유하겠습니다." in turn
    assert "다음 주에 시작하겠습니다." in turn
    assert "alignment_uncertain" in turn
    assert "overlap" in turn
    if with_analysis:
        assert "분석 버전: analysis-1" in markdown
        assert "분석 기준 전사: version-1" in markdown
        assert "초안을 공유한다. (근거: t2)" in markdown
        assert "공유 시간을 정해야 한다. (근거: t2)" in markdown
        assert "담당: 화자 B / 기한: 18일" in markdown
    else:
        assert "분석 버전: 없음" in markdown
        assert "초안을 공유한다." not in markdown
