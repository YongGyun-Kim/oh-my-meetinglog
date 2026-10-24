from meetinglog.domain import AnalysisBody, Speaker, SpeechResult, SpeechSegment, Transcript

Turn = SpeechSegment


def transcript_fixture(recording_id="recording"):
    return Transcript(
        id="version-1",
        recording_id=recording_id,
        speakers=[Speaker(id="a", display_name="화자 A"), Speaker(id="b", display_name="화자 B")],
        turns=[
            Turn(
                id="t1",
                start_ms=0,
                end_ms=2000,
                speaker_id="a",
                text_original="언제 서비스를 시작할까요?",
            ),
            Turn(
                id="t2",
                start_ms=2200,
                end_ms=5000,
                speaker_id="b",
                text_original="다음 주에 시작하겠습니다.",
            ),
        ],
    )


def analysis_fixture():
    return AnalysisBody.model_validate(
        {
            "overview": {
                "kind": "interview",
                "summary": {
                    "text": "서비스 시작 일정을 논의했다.",
                    "evidence_sentence_ids": ["t1", "t2"],
                },
                "main_topics": [
                    {"text": "서비스 시작 일정", "evidence_sentence_ids": ["t1", "t2"]}
                ],
            },
            "topics": [
                {
                    "title": "시작 일정",
                    "start_ms": 0,
                    "end_ms": 5000,
                    "discussion": [
                        {"text": "다음 주 시작을 제안했다.", "evidence_sentence_ids": ["t2"]}
                    ],
                    "different_views": [],
                    "conclusion": None,
                    "evidence_sentence_ids": ["t1", "t2"],
                }
            ],
            "question_answers": [
                {
                    "question": {"text": "서비스 시작 시점", "evidence_sentence_ids": ["t1"]},
                    "answer": {"text": "다음 주에 시작한다.", "evidence_sentence_ids": ["t2"]},
                }
            ],
            "agreements": [],
            "open_questions": [],
            "actions": [],
        }
    )


def as_speech(transcript):
    return SpeechResult(
        provider="test",
        model="fixed",
        speakers=transcript.speakers,
        turns=[
            SpeechSegment(**sentence.model_dump(), speaker_id=speaker_id)
            for speaker_id, sentence in transcript.entries()
        ],
    )


def form_analysis_fixture(form="meeting"):
    from meetinglog.domain import AnalysisSection, Fact, FormAnalysisBody, ParagraphGroup

    first, second, actions = {
        "meeting": ("회의 결과", "안건별 논의", "후속 조치"),
        "project": ("목표", "요구사항", "후속 조치"),
        "decision": ("결정 결과", "판단 기준", "후속 조치"),
        "progress": ("현재 상태", "진행 중인 일", "다음 할 일"),
        "interview": ("사용자 상황", "경험과 문제", "후속 조치"),
    }[form]
    body = FormAnalysisBody(
        sections=[
            AnalysisSection(
                title=first,
                groups=[
                    ParagraphGroup(
                        title=None,
                        paragraphs=[
                            Fact(
                                text="서비스 시작 일정을 논의했다.",
                                evidence_sentence_ids=["t1", "t2"],
                            )
                        ],
                    )
                ],
            ),
            AnalysisSection(
                title=second,
                groups=[
                    ParagraphGroup(
                        title="서비스 시작",
                        paragraphs=[Fact(text="다음 주에 시작한다.", evidence_sentence_ids=["t2"])],
                    )
                ],
            ),
            AnalysisSection(title=actions),
        ]
    )

    if form == "decision":
        from meetinglog.domain import OptionComparison

        body.sections.insert(
            2,
            AnalysisSection(
                title="선택지 비교",
                comparisons=[
                    OptionComparison(
                        option="다음 주 시작",
                        points=[Fact(text="빠르게 시작하는 안이다.", evidence_sentence_ids=["t2"])],
                    ),
                    OptionComparison(
                        option="일정 추가 검토",
                        points=[
                            Fact(
                                text="시작 시점을 더 검토하는 안이다.", evidence_sentence_ids=["t1"]
                            )
                        ],
                    ),
                ],
            ),
        )
    return body
