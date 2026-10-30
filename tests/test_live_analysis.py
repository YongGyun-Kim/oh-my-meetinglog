import os
from pathlib import Path

import pytest
from meetinglog.analysis.service import analyze_with
from meetinglog.config import Settings
from meetinglog.domain import Transcript
from meetinglog.engines.local_analysis import LocalAnalysis, unload_ollama


@pytest.mark.live
@pytest.mark.parametrize("form", ["meeting", "project", "decision", "progress", "interview"])
def test_local_analysis_completes_real_transcript(form):
    source = os.environ.get("MEETINGLOG_TEST_TRANSCRIPT")
    if not source:
        pytest.skip("MEETINGLOG_TEST_TRANSCRIPT에 테스트할 전사 JSON 경로를 지정한다.")
    transcript = Transcript.model_validate_json(Path(source).read_text())
    settings = Settings()
    engine = LocalAnalysis(settings, form=form)
    try:
        body = analyze_with(
            engine,
            transcript,
            form=form,
            progress=lambda completed, total: print(f"{form}: {completed}/{total}", flush=True),
        )
        assert any(
            fact.text.strip()
            for section in body.sections
            for fact in [
                *[fact for group in section.groups for fact in group.paragraphs],
                *[fact for choice in section.comparisons for fact in choice.points],
                *section.actions,
            ]
        )
    finally:
        engine.client.close()
        unload_ollama(settings)
