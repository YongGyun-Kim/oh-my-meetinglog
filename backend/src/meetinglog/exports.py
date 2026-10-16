import html
import json

from meetinglog.db import ApiError, Database, require_recording
from meetinglog.domain import AnalysisVersion
from meetinglog.recordings.service import as_recording
from meetinglog.transcripts.repository import TranscriptRepository


class Exporter:
    def __init__(self, db: Database):
        self.db = db

    def payload(
        self, recording_id: str, transcript_id: str | None = None, analysis_id: str | None = None
    ) -> dict:
        with self.db.session() as connection:
            record = require_recording(connection, recording_id)
            transcript_id = transcript_id or record["current_transcript_id"]
            if not transcript_id:
                raise ApiError("transcript_not_ready", "전사가 완료된 뒤 내보낼 수 있습니다", 409)
            transcript = TranscriptRepository(self.db).read(connection, transcript_id)
            if transcript.recording_id != recording_id:
                raise ApiError("not_found", "전사 버전을 찾을 수 없습니다", 404)
            if analysis_id:
                analysis_row = connection.execute(
                    "SELECT * FROM analyses WHERE id=? AND recording_id=?",
                    (analysis_id, recording_id),
                ).fetchone()
                if analysis_row is None:
                    raise ApiError("not_found", "분석 버전을 찾을 수 없습니다", 404)
                if analysis_row["transcript_id"] != transcript_id:
                    raise ApiError("version_conflict", "전사와 분석의 기준 버전이 다릅니다", 409)
            else:
                analysis_row = connection.execute(
                    "SELECT * FROM analyses WHERE recording_id=? AND transcript_id=? ORDER BY created_at DESC LIMIT 1",
                    (recording_id, transcript_id),
                ).fetchone()
            analysis = (
                AnalysisVersion.model_validate_json(analysis_row["payload"])
                if analysis_row
                else None
            )
            history = []
            for row in connection.execute(
                "SELECT j.kind,j.mode,j.state,e.stage,e.event,e.created_at,e.metadata FROM job_events e JOIN jobs j ON j.id=e.job_id WHERE j.recording_id=? ORDER BY e.id",
                (recording_id,),
            ):
                metadata = json.loads(row["metadata"])
                allowed = {
                    key: value
                    for key, value in metadata.items()
                    if key
                    in (
                        "provider",
                        "model",
                        "location",
                        "quality",
                        "fallback_reason",
                        "reason",
                        "attempt",
                        "duplicate_cost_possible",
                    )
                }
                history.append(
                    {
                        "kind": row["kind"],
                        "mode": row["mode"],
                        "state": row["state"],
                        "stage": row["stage"],
                        "event": row["event"],
                        "created_at": row["created_at"],
                        "metadata": allowed,
                    }
                )
            return {
                "schema_version": 1,
                "recording": as_recording(record).model_dump(mode="json"),
                "transcript": transcript.model_dump(mode="json"),
                "analysis": analysis.model_dump(mode="json") if analysis else None,
                "processing_history": history,
            }

    @staticmethod
    def markdown(payload: dict) -> str:
        recording, transcript, analysis = (
            payload["recording"],
            payload["transcript"],
            payload["analysis"],
        )

        def clean(text):
            return html.escape(str(text), quote=False)

        lines = [
            f"# {clean(recording['title'])}",
            "",
            f"녹음 시각: {recording['created_at']}",
            f"전사 버전: {transcript['id']}",
            "",
        ]
        speakers = {speaker["id"]: speaker["display_name"] for speaker in transcript["speakers"]}
        if speakers:
            lines += ["## 화자", "", *[f"- {clean(name)}" for name in speakers.values()], ""]

        def fact(item):
            return f"{clean(item['text'])} (근거: {', '.join(item['evidence_turn_ids'])})"

        if analysis:
            body = analysis["body"]
            lines += ["## 전체 요약", "", fact(body["overview"]["summary"]), ""]
            for topic in body["topics"]:
                lines += [
                    f"### {clean(topic['title'])}",
                    "",
                    *[f"- {fact(item)}" for item in topic["discussion"]],
                    "",
                ]
                if topic["different_views"]:
                    lines += [
                        "서로 다른 의견",
                        "",
                        *[f"- {fact(item)}" for item in topic["different_views"]],
                        "",
                    ]
                if topic["conclusion"]:
                    lines += [fact(topic["conclusion"]), ""]
            for label, key in [
                ("질문과 답변", "question_answers"),
                ("합의", "agreements"),
                ("미해결 질문", "open_questions"),
                ("후속 할 일", "actions"),
            ]:
                if not body[key]:
                    continue
                lines += [f"## {label}", ""]
                for item in body[key]:
                    if key == "question_answers":
                        lines += [
                            f"- 질문: {fact(item['question'])}",
                            f"  답변: {fact(item['answer']) if item['answer'] else '답변 없음'}",
                        ]
                    elif key == "actions":
                        owner = speakers.get(item["owner_speaker_id"], "미지정")
                        lines.append(
                            f"- {fact(item)} / 담당: {clean(owner)} / 기한: {clean(item['due_text'] or '미지정')}"
                        )
                    else:
                        lines.append(f"- {fact(item)}")
                lines.append("")
        lines += ["## 전사", ""]
        for turn in transcript["turns"]:
            seconds = turn["start_ms"] // 1000
            timestamp = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
            lines += [
                f"**{timestamp} {clean(speakers.get(turn['speaker_id'], '화자 미확인'))}**",
                "",
                clean(turn["text_edited"] or turn["text_original"]),
                "",
            ]
        return "\n".join(lines)
