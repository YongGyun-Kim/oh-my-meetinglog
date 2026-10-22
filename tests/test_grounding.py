import pytest

from tests.analysis_fixtures import analysis_fixture, transcript_fixture


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
