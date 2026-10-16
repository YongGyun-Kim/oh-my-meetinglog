import pytest

from tests.analysis_fixtures import analysis_fixture, transcript_fixture


def test_unknown_citation_and_owner_are_rejected():
    from meetinglog.analysis.grounding import GroundingError, validate_grounding
    from meetinglog.domain import Action

    transcript = transcript_fixture()
    body = analysis_fixture()
    validate_grounding(body, transcript)
    body.overview.summary.evidence_turn_ids = ["missing-turn"]
    with pytest.raises(GroundingError) as error:
        validate_grounding(body, transcript)
    assert error.value.code == "unknown_turn"
    body = analysis_fixture()
    body.actions = [
        Action(
            text="시작하기", owner_speaker_id="invented", due_text=None, evidence_turn_ids=["t2"]
        )
    ]
    with pytest.raises(GroundingError) as error:
        validate_grounding(body, transcript)
    assert error.value.code == "unknown_speaker"


def test_topic_outside_recording_and_unspoken_due_date_are_rejected():
    from meetinglog.analysis.grounding import GroundingError, validate_grounding
    from meetinglog.domain import Action

    body, transcript = analysis_fixture(), transcript_fixture()
    body.topics[0].end_ms = 9000
    with pytest.raises(GroundingError):
        validate_grounding(body, transcript)
    body = analysis_fixture()
    body.actions = [
        Action(
            text="시작하기",
            owner_speaker_id="b",
            due_text="2027년 1월 1일",
            evidence_turn_ids=["t2"],
        )
    ]
    with pytest.raises(GroundingError):
        validate_grounding(body, transcript)
