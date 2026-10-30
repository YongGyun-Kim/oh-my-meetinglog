import pytest

from tests.analysis_fixtures import analysis_fixture, transcript_fixture


@pytest.mark.parametrize(
    "code",
    ["empty_analysis", "invalid_section", "invalid_comparison", "invalid_actions", "empty_action"],
)
def test_empty_or_malformed_analysis_is_not_reported_as_a_citation_mismatch(code):
    from meetinglog.analysis.grounding import GroundingError

    error = GroundingError(code)
    assert error.code == code
    assert "근거" not in error.message
    assert "다시" in error.message
    assert error.message != GroundingError("unknown_sentence").message


def test_unknown_citation_and_owner_are_rejected():
    from meetinglog.analysis.grounding import GroundingError, validate_grounding
    from meetinglog.domain import Action

    transcript = transcript_fixture()
    body = analysis_fixture()
    validate_grounding(body, transcript)
    body.overview.summary.evidence_sentence_ids = ["missing-turn"]
    with pytest.raises(GroundingError) as error:
        validate_grounding(body, transcript)
    assert error.value.code == "unknown_sentence"
    body = analysis_fixture()
    body.actions = [
        Action(
            text="시작하기",
            owner_speaker_id="invented",
            due_text=None,
            evidence_sentence_ids=["t2"],
        )
    ]
    with pytest.raises(GroundingError) as error:
        validate_grounding(body, transcript)
    assert error.value.code == "unknown_speaker"


def test_unspoken_due_date_is_rejected():
    from meetinglog.analysis.grounding import GroundingError, validate_grounding
    from meetinglog.domain import Action

    body, transcript = analysis_fixture(), transcript_fixture()
    body.actions = [
        Action(
            text="시작하기",
            owner_speaker_id="b",
            due_text="2027년 1월 1일",
            evidence_sentence_ids=["t2"],
        )
    ]
    with pytest.raises(GroundingError):
        validate_grounding(body, transcript)


@pytest.mark.parametrize(
    "speaker_id, owner, code", [("b", "화자 B", "ambiguous_owner"), (None, "s2", "unspoken_owner")]
)
def test_owner_retry_identifies_the_action_and_incorrect_owner(speaker_id, owner, code):
    from meetinglog.analysis.grounding import GroundingError, validate_grounding
    from meetinglog.domain import FormAction

    from tests.analysis_fixtures import form_analysis_fixture

    body = form_analysis_fixture()
    body.sections[2].actions = [
        FormAction(
            text="서비스 시작",
            owner_speaker_id=speaker_id,
            owner_text=owner,
            due_text=None,
            evidence_sentence_ids=["t2"],
        )
    ]
    with pytest.raises(GroundingError) as error:
        validate_grounding(body, transcript_fixture())
    assert error.value.code == code
    assert "서비스 시작" in error.value.feedback
    assert owner in error.value.feedback
    assert "t2" in error.value.feedback


def test_retry_reports_all_incorrect_action_owners_in_one_correction():
    from meetinglog.analysis.grounding import GroundingError, validate_grounding
    from meetinglog.domain import FormAction

    from tests.analysis_fixtures import form_analysis_fixture

    body = form_analysis_fixture()
    body.sections[2].actions = [
        FormAction(
            text="첫 작업",
            owner_speaker_id=None,
            owner_text="화자 A",
            due_text=None,
            evidence_sentence_ids=["t1"],
        ),
        FormAction(
            text="둘째 작업",
            owner_speaker_id=None,
            owner_text="화자 B",
            due_text=None,
            evidence_sentence_ids=["t2"],
        ),
    ]
    with pytest.raises(GroundingError) as error:
        validate_grounding(body, transcript_fixture())
    assert error.value.code == "unspoken_owner"
    assert all(
        text in error.value.feedback
        for text in ("첫 작업", "화자 A", "t1", "둘째 작업", "화자 B", "t2")
    )
