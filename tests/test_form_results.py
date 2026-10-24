import json

import httpx
import pytest

from tests.analysis_fixtures import analysis_fixture, transcript_fixture


def form_data(title="회의 결과", text="다음 주에 서비스를 시작한다.", ids=None):
    return {
        "sections": [
            {
                "title": title,
                "groups": [
                    {
                        "title": "서비스 시작",
                        "paragraphs": [{"text": text, "evidence_sentence_ids": ids or ["t2"]}],
                    }
                ],
                "comparisons": [],
                "actions": [],
            }
        ]
    }


def test_new_and_legacy_analysis_versions_round_trip():
    from meetinglog.domain import AnalysisVersion, FormAnalysisBody

    for body in (analysis_fixture(), FormAnalysisBody.model_validate(form_data())):
        version = AnalysisVersion(
            id="a", transcript_id="t", body=body, provider="test", model="fixed", prompt_version="4"
        )
        assert AnalysisVersion.model_validate_json(version.model_dump_json()).body == body


def test_project_keeps_required_unknown_fields_and_hides_empty_optional_sections():
    from meetinglog.analysis.forms import canonicalize
    from meetinglog.domain import FormAnalysisBody

    data = form_data("요구사항")
    data["sections"].append({"title": "제약", "groups": [], "comparisons": [], "actions": []})
    partial = canonicalize(FormAnalysisBody.model_validate(data), "project", final=False)
    assert [s.title for s in partial.sections] == ["요구사항"]
    result = canonicalize(partial, "project")
    assert [s.title for s in result.sections] == ["목표", "요구사항", "예산", "일정"]
    assert not result.sections[-1].groups


@pytest.mark.parametrize("title", ["대화 개요", "채용 평가", "임의 지시"])
def test_form_rejects_sections_outside_its_contract(title):
    from meetinglog.analysis.forms import canonicalize
    from meetinglog.analysis.grounding import GroundingError
    from meetinglog.domain import FormAnalysisBody

    with pytest.raises(GroundingError):
        canonicalize(FormAnalysisBody.model_validate(form_data(title)), "meeting")


def test_comparison_requires_two_options_and_is_only_allowed_in_decision_form():
    from meetinglog.analysis.forms import canonicalize
    from meetinglog.analysis.grounding import GroundingError
    from meetinglog.domain import FormAnalysisBody

    data = {
        "sections": [
            {
                "title": "선택지 비교",
                "groups": [],
                "actions": [],
                "comparisons": [
                    {
                        "option": "안 A",
                        "points": [
                            {
                                "text": "운영 비용이 낮다고 평가했다.",
                                "evidence_sentence_ids": ["t1"],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    with pytest.raises(GroundingError):
        canonicalize(FormAnalysisBody.model_validate(data), "decision")
    data["sections"][0]["comparisons"].append(
        {
            "option": "안 B",
            "points": [{"text": "추가 검토가 필요하다.", "evidence_sentence_ids": ["t2"]}],
        }
    )
    assert (
        len(canonicalize(FormAnalysisBody.model_validate(data), "decision").sections[0].comparisons)
        == 2
    )
    data["sections"][0]["title"] = "안건별 논의"
    with pytest.raises(GroundingError):
        canonicalize(FormAnalysisBody.model_validate(data), "meeting")


def test_external_owner_and_due_date_must_be_supported_by_action_evidence():
    from meetinglog.analysis.grounding import GroundingError, validate_grounding
    from meetinglog.domain import FormAnalysisBody

    transcript = transcript_fixture()
    transcript.turns[1].sentences[0].text_original = "김 대리가 다음 주에 시작하겠습니다."
    data = {
        "sections": [
            {
                "title": "후속 조치",
                "groups": [],
                "comparisons": [],
                "actions": [
                    {
                        "text": "서비스 시작",
                        "owner_speaker_id": None,
                        "owner_text": "김 대리",
                        "due_text": "다음 주",
                        "evidence_sentence_ids": ["t2"],
                    }
                ],
            }
        ]
    }
    body = FormAnalysisBody.model_validate(data)
    validate_grounding(body, transcript)
    body.actions[0].owner_speaker_id = "b"
    with pytest.raises(GroundingError):
        validate_grounding(body, transcript)
    body.actions[0].owner_speaker_id = None
    body.actions[0].owner_text = "박 대리"
    with pytest.raises(GroundingError):
        validate_grounding(body, transcript)
    body.actions[0].owner_text = "김 대리"
    body.actions[0].due_text = "내일"
    with pytest.raises(GroundingError):
        validate_grounding(body, transcript)


def test_local_provider_requests_new_form_contract(settings):
    from meetinglog.analysis.input import prepare_input
    from meetinglog.engines.local_analysis import LocalAnalysis

    def handler(request):
        payload = json.loads(request.content)
        assert set(payload["format"]["properties"]) == {"sections"}
        assert "요구사항 협의" in payload["messages"][1]["content"]
        assert "start_ms" not in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps(form_data("요구사항"), ensure_ascii=False)}},
        )

    client = httpx.Client(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    result = LocalAnalysis(settings, client, form="project").generate(
        prepare_input(transcript_fixture())[0]
    )
    assert result.sections[0].title == "요구사항"


def test_merge_is_retried_when_it_invents_a_reference_and_preserves_later_budget(monkeypatch):
    from meetinglog.analysis import service
    from meetinglog.domain import FormAnalysisBody

    transcript = transcript_fixture()
    transcript.turns[0].sentences[0].id = "original-first"
    transcript.turns[1].sentences[0].id = "original-second"
    transcript.turns[1].sentences[0].text_original = "예산은 500만 원입니다."
    monkeypatch.setattr(
        service,
        "chunk_input",
        lambda data, form: [data.model_copy(update={"lines": [line]}) for line in data.lines],
    )
    seen = []

    class Engine:
        def generate(self, part, feedback=None):
            title = "요구사항" if part.lines[0].id == "t1" else "예산"
            return FormAnalysisBody.model_validate(
                form_data(title, part.lines[0].text, [part.lines[0].id])
            )

        def merge(self, bodies, feedback=None):
            seen.append(feedback)
            assert [s.title for b in bodies for s in b.sections] == ["요구사항", "예산"]
            if feedback is None:
                return FormAnalysisBody.model_validate(form_data("예산", ids=["invented"]))
            return FormAnalysisBody(sections=[s for b in bodies for s in b.sections])

    result = service.analyze_with(Engine(), transcript, form="project")
    assert len(seen) == 2
    budget = next(s for s in result.sections if s.title == "예산")
    assert budget.groups[0].paragraphs[0].text == "예산은 500만 원입니다."
    assert budget.groups[0].paragraphs[0].evidence_sentence_ids == ["original-second"]


def test_structured_markdown_preserves_sections_unknowns_comparisons_and_external_owner():
    from meetinglog.exports import Exporter

    body = {
        "sections": [
            {"title": "예산", "groups": [], "comparisons": [], "actions": []},
            {
                "title": "선택지 비교",
                "groups": [],
                "actions": [],
                "comparisons": [
                    {
                        "option": "A|B",
                        "points": [{"text": "<script> 비용", "evidence_sentence_ids": ["t1"]}],
                    },
                    {
                        "option": "C",
                        "points": [{"text": "운영 편의", "evidence_sentence_ids": ["t2"]}],
                    },
                ],
            },
            {
                "title": "후속 조치",
                "groups": [],
                "comparisons": [],
                "actions": [
                    {
                        "text": "시작",
                        "owner_speaker_id": None,
                        "owner_text": "김 대리",
                        "due_text": "다음 주",
                        "evidence_sentence_ids": ["t2"],
                    }
                ],
            },
        ]
    }
    payload = {
        "recording": {"id": "r", "title": "기록", "created_at": "now"},
        "transcript": transcript_fixture().model_dump(),
        "analysis": {"id": "a", "transcript_id": "t", "form": "decision", "body": body},
    }
    markdown = Exporter.markdown(payload)
    assert "## 예산\n\n언급 없음" in markdown
    assert "| 선택지 | 검토 내용 |" in markdown
    assert "A\\|B" in markdown
    assert "<script>" not in markdown
    assert "담당: 김 대리" in markdown
    assert "## 질문과 답변" not in markdown


def test_empty_result_and_actions_hidden_in_paragraphs_are_rejected():
    from meetinglog.analysis.forms import canonicalize
    from meetinglog.analysis.grounding import GroundingError
    from meetinglog.domain import FormAnalysisBody

    with pytest.raises(GroundingError):
        canonicalize(FormAnalysisBody(sections=[]), "project")
    with pytest.raises(GroundingError):
        canonicalize(FormAnalysisBody.model_validate(form_data("후속 조치")), "meeting")


def test_cloud_generation_and_merge_use_same_form_contract(settings):
    from types import SimpleNamespace

    from meetinglog.analysis.input import prepare_input
    from meetinglog.domain import FormAnalysisBody
    from meetinglog.engines.cloud_analysis import CloudAnalysis

    response = FormAnalysisBody.model_validate(form_data("현재 상태"))
    calls = []

    def parse(**request):
        calls.append(request)
        assert request["text_format"] is FormAnalysisBody
        assert "진행 점검" in request["input"][1]["content"]
        return SimpleNamespace(output_parsed=response)

    engine = CloudAnalysis(
        settings, SimpleNamespace(responses=SimpleNamespace(parse=parse)), "progress"
    )
    generated = engine.generate(prepare_input(transcript_fixture())[0])
    merged = engine.merge([generated, generated], "unknown_sentence")
    assert merged == response
    assert "unknown_sentence" in calls[-1]["input"][1]["content"]


def test_merge_prompt_refuses_oversized_results():
    from meetinglog.analysis.prompts import merge_messages
    from meetinglog.db import ApiError
    from meetinglog.domain import FormAnalysisBody

    body = FormAnalysisBody.model_validate(form_data(text="긴 결과" * 10000))
    with pytest.raises(ApiError) as error:
        merge_messages([body, body], "meeting")
    assert error.value.code == "context_limit"
