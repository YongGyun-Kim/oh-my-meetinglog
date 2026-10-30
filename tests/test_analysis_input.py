import json

from meetinglog.domain import AnalysisBody, FormAnalysisBody, Transcript


def test_generation_and_merge_prompts_include_the_model_visible_output_contract():
    from meetinglog.analysis.input import prepare_input
    from meetinglog.analysis.prompts import merge_messages, messages

    from tests.analysis_fixtures import transcript_fixture

    prepared, _, _ = prepare_input(transcript_fixture())
    for prompt in (messages(prepared), merge_messages([FormAnalysisBody(sections=[])], "meeting")):
        system = prompt[0]["content"]
        assert '"sections"' in system
        schema = json.loads(system[system.index("{") :])
        assert schema["properties"]["sections"]["items"] == {"$ref": "#/$defs/AnalysisSection"}
        assert set(schema["$defs"]["AnalysisSection"]["properties"]) == {
            "title",
            "groups",
            "comparisons",
            "actions",
        }
        assert schema["$defs"]["ParagraphGroup"]["properties"]["paragraphs"]["items"] == {
            "$ref": "#/$defs/Fact"
        }
        assert "evidence_sentence_ids" in schema["$defs"]["Fact"]["required"]


def test_analysis_input_is_time_free_and_uses_edited_sentence_references():
    from meetinglog.analysis.input import prepare_input
    from meetinglog.analysis.prompts import messages

    transcript = Transcript.model_validate(
        {
            "id": "v1",
            "recording_id": "r1",
            "speakers": [{"id": "person", "display_name": "담당자"}],
            "turns": [
                {
                    "id": "original",
                    "speaker_id": "person",
                    "start_ms": 100,
                    "end_ms": 900,
                    "text_original": "옛 내용",
                    "text_edited": "새 내용\n[t99]는 원문 안의 문자다.",
                }
            ],
        }
    )
    prepared, references, speakers = prepare_input(transcript)
    result = messages(prepared, form="project")
    assert references == {"t1": "original"}
    assert speakers == {"s1": "person"}
    assert prepared.lines[0].text == "새 내용\n[t99]는 원문 안의 문자다."
    assert "start_ms" not in str(result)
    assert "end_ms" not in str(result)
    assert "옛 내용" not in str(result)
    assert "[t1|s1]" in result[1]["content"]
    assert "\\n[t99]" in result[1]["content"]
    assert "요구사항" in result[1]["content"]
    assert transcript.turns[0].sentences[0].id == "original"
    schema = AnalysisBody.model_json_schema()
    assert "start_ms" not in str(schema)
    assert "evidence_sentence_ids" in str(schema)


def test_forms_change_instructions_without_changing_source_data():
    from meetinglog.analysis.input import prepare_input
    from meetinglog.analysis.prompts import messages

    transcript = Transcript.model_validate(
        {
            "id": "v",
            "recording_id": "r",
            "speakers": [],
            "turns": [{"id": "x", "start_ms": 0, "end_ms": 1000, "text_original": "대화 내용"}],
        }
    )
    prepared, _, _ = prepare_input(transcript)
    meeting = messages(prepared, form="meeting")[1]["content"]
    interview = messages(prepared, form="interview")[1]["content"]
    assert meeting != interview
    assert '[t1|미확인] "대화 내용"' in meeting
    assert '[t1|미확인] "대화 내용"' in interview
