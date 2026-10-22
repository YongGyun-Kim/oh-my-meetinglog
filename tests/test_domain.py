import pytest
from pydantic import ValidationError


@pytest.mark.parametrize("start,end", [(-1, 2), (2, 1), (2, 2)])
def test_invalid_turn_time_is_rejected(start, end):
    from meetinglog.domain import Sentence as Turn

    with pytest.raises(ValidationError):
        Turn(id="turn-1", start_ms=start, end_ms=end, text_original="안녕하세요")


def test_duplicate_turn_ids_are_rejected():
    from meetinglog.domain import SpeechSegment as Turn
    from meetinglog.domain import Transcript

    turn = Turn(id="same", start_ms=0, end_ms=100, text_original="네")
    with pytest.raises(ValidationError):
        Transcript(id="v1", recording_id="r1", turns=[turn, turn], speakers=[])
