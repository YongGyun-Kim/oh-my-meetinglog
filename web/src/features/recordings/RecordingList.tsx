import { ArrowUpRight, FileAudio, Mic, Search } from "lucide-react";
import { useState } from "react";
import { clock } from "../../lib/api";
import type { RecordingSummary } from "../../lib/types";

export function status(record: RecordingSummary) {
  if (record.input_state === "invalid") return "파일 확인 필요";
  if (record.input_state !== "ready") return "저장 미완료";
  if (record.job_state === "succeeded")
    return record.job_stage === "no_speech" ? "음성 없음" : "정리 완료";
  if (record.job_state === "failed") return "처리 실패";
  if (record.job_state === "cancelled") return "처리 취소";
  if (record.job_state === "running")
    return record.job_stage === "analysis" ? "대화 정리 중" : "전사 중";
  return "처리 대기";
}
export function RecordingList({
  records,
  loading,
  onSelect,
  onUpload,
}: {
  records: RecordingSummary[];
  loading: boolean;
  onSelect: (id: string) => void;
  onUpload: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = records.filter((record) =>
    record.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  );
  return (
    <section className="library">
      <div className="section-heading">
        <h2>
          모든 기록 <span>{records.length}</span>
        </h2>
        <label className="search">
          <Search size={16} />
          <input
            aria-label="기록 검색"
            placeholder="제목으로 검색"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
      </div>
      <div className="table-heading">
        <span>대화</span>
        <span>날짜</span>
        <span>길이</span>
        <span>상태</span>
        <span />
      </div>
      {loading && !records.length ? (
        <p className="empty-message">기록을 불러오고 있습니다…</p>
      ) : !filtered.length ? (
        <div className="empty-state">
          <FileAudio size={36} strokeWidth={1.2} />
          <h3>{query ? "검색 결과가 없습니다" : "첫 대화를 남겨보세요"}</h3>
          <p>
            {query
              ? "다른 제목으로 검색해 주세요."
              : "녹음이 끝나면 화자별 전사와 대화 요약이 여기에 모입니다."}
          </p>
          {!query && (
            <button className="button secondary" onClick={onUpload}>
              녹음 파일 가져오기 <ArrowUpRight size={16} />
            </button>
          )}
        </div>
      ) : (
        filtered.map((record) => (
          <button
            className="record-row"
            key={record.id}
            onClick={() => onSelect(record.id)}
          >
            <span className="record-name">
              <span className="file-icon">
                {record.source === "microphone" ? (
                  <Mic size={19} />
                ) : (
                  <FileAudio size={19} />
                )}
              </span>
              <span>
                <strong>{record.title}</strong>
                <small>
                  {record.source === "microphone"
                    ? "마이크 녹음"
                    : "가져온 파일"}
                </small>
              </span>
            </span>
            <span className="record-date">
              {record.created_at
                ? new Intl.DateTimeFormat("ko-KR", {
                    month: "short",
                    day: "numeric",
                  }).format(new Date(record.created_at))
                : "—"}
            </span>
            <span className="time muted">
              {record.duration_ms ? clock(record.duration_ms) : "—"}
            </span>
            <span className={`status ${record.job_state ?? ""}`}>
              {status(record)}
            </span>
            <ArrowUpRight className="row-arrow" size={17} />
          </button>
        ))
      )}
    </section>
  );
}
