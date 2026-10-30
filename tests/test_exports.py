import pytest
from meetinglog.analysis.service import AnalysisService
from meetinglog.domain import Action, AnalysisVersion, Fact, FormAction, Recording
from meetinglog.exports import Exporter
from meetinglog.jobs.repository import JobRepository

from tests.analysis_fixtures import analysis_fixture, form_analysis_fixture, transcript_fixture
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


@pytest.mark.parametrize("structured", [True, False])
def test_analysis_markdown_download_contains_only_saved_summary(settings, db, tmp_path, structured):
    client, record_id, transcript = populated_client(settings, db, tmp_path)
    try:
        body = form_analysis_fixture("decision") if structured else analysis_fixture()
        action = dict(
            text="초안 공유",
            owner_speaker_id=transcript.speakers[1].id,
            due_text="다음 주",
            evidence_sentence_ids=["t2"],
        )
        if structured:
            body.sections[0].groups[0].paragraphs.append(
                Fact(text="<script> 추가 논의", evidence_sentence_ids=["t1"])
            )
            body.sections[-1].actions = [FormAction(**action, owner_text=None)]
        else:
            body.actions = [Action(**action)]
            body.overview.main_topics = [
                Fact(text="핵심 주제에만 저장된 예산 검토", evidence_sentence_ids=["t1"])
            ]
        client.post(
            f"/api/recordings/{record_id}/analyze",
            json={
                "mode": "local_only",
                "transcript_id": transcript.id,
                "form": "decision" if structured else "meeting",
            },
        ).raise_for_status()
        jobs = JobRepository(db)
        job = jobs.claim()
        version = AnalysisVersion(
            id="saved-analysis",
            transcript_id=transcript.id,
            body=body,
            form="decision" if structured else "meeting",
            provider="test",
            model="fixed",
            prompt_version="1",
        )
        artifact = tmp_path / "analysis.json"
        artifact.write_text(version.model_dump_json())
        AnalysisService(db).publish(job, artifact)
        jobs.finish(job.id, "succeeded")

        response = client.get(f"/api/recordings/{record_id}/export?format=analysis_markdown")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert response.headers["content-disposition"].endswith(f'{record_id}-analysis.md"')
        markdown = response.text
        assert markdown.startswith("# 인터뷰\n\n")
        assert "서비스 시작 일정을 논의했다." in markdown
        assert "초안 공유 / 담당: 화자 B / 기한: 다음 주" in markdown
        for excluded in [
            "## 전사",
            "## 화자",
            "근거:",
            "자료 해석 기준",
            transcript.id,
            version.id,
            "언제 서비스를 시작할까요?",
            "다음 주에 시작하겠습니다.",
        ]:
            assert excluded not in markdown
        if structured:
            assert (
                "## 결정 결과\n\n서비스 시작 일정을 논의했다.\n\n&lt;script&gt; 추가 논의"
                in markdown
            )
            assert "### 서비스 시작" in markdown
            assert "| 다음 주 시작 | 빠르게 시작하는 안이다. |" in markdown
        else:
            assert "## 전체 요약" in markdown
            assert "## 핵심 주제\n\n- 핵심 주제에만 저장된 예산 검토" in markdown
            assert "질문: 서비스 시작 시점" in markdown
    finally:
        client.__exit__(None, None, None)


def test_analysis_markdown_requires_saved_analysis(settings, db, tmp_path):
    client, record_id, _ = populated_client(settings, db, tmp_path)
    try:
        response = client.get(f"/api/recordings/{record_id}/export?format=analysis_markdown")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "analysis_not_ready"
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
