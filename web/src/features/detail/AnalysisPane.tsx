import { clock } from "../../lib/api";
import type { Analysis, Fact, Transcript } from "../../lib/types";

export function AnalysisPane({
  analysis,
  transcript,
  onEvidence,
}: {
  analysis: Analysis;
  transcript: Transcript | null;
  onEvidence: (id: string) => void;
}) {
  const body = analysis.body;
  const citations = (ids: string[]) => (
    <span className="citations">
      {ids.map((id) => {
        const turn = transcript?.turns.find((item) => item.id === id);
        const name =
          transcript?.speakers.find((item) => item.id === turn?.speaker_id)
            ?.display_name ?? "미확인 화자";
        return turn ? (
          <button
            key={id}
            aria-label={`근거 ${clock(turn.start_ms)} ${name}`}
            onClick={() => onEvidence(id)}
          >
            {clock(turn.start_ms)} {name}
          </button>
        ) : null;
      })}
    </span>
  );
  const fact = (item: Fact, index: number) => (
    <div className="analysis-fact" key={index}>
      <p>{item.text}</p>
      {citations(item.evidence_turn_ids)}
    </div>
  );
  const kind = {
    interview: "인터뷰",
    counseling: "상담",
    conversation: "대화",
    unknown: "대화 유형 미확인",
  }[body.overview.kind];
  return (
    <div className="analysis-scroll">
      <div className="analysis-intro">
        <span className="kind-label">{kind}</span>
        <h3>대화 개요</h3>
        {fact(body.overview.summary, 0)}
      </div>
      {!!body.overview.main_topics.length && (
        <section className="analysis-section">
          <h3>핵심 주제</h3>
          {body.overview.main_topics.map(fact)}
        </section>
      )}
      {!!body.topics.length && (
        <section className="analysis-section">
          <h3>대화의 흐름</h3>
          {body.topics.map((topic, index) => (
            <article className="topic" key={index}>
              <div className="topic-title">
                <span>{String(index + 1).padStart(2, "0")}</span>
                <h4>{topic.title}</h4>
                <small>
                  {clock(topic.start_ms)}–{clock(topic.end_ms)}
                </small>
              </div>
              {topic.discussion.map(fact)}
              {!!topic.different_views.length && (
                <div className="different-views">
                  <h5>서로 다른 의견</h5>
                  {topic.different_views.map(fact)}
                </div>
              )}
              {topic.conclusion && (
                <div className="conclusion">{fact(topic.conclusion, 0)}</div>
              )}
            </article>
          ))}
        </section>
      )}
      {!!body.question_answers.length && (
        <section className="analysis-section">
          <h3>질문과 답변</h3>
          {body.question_answers.map((qa, index) => (
            <div className="qa" key={index}>
              <div>
                <span>Q</span>
                {fact(qa.question, 0)}
              </div>
              {qa.answer && (
                <div>
                  <span>A</span>
                  {fact(qa.answer, 0)}
                </div>
              )}
            </div>
          ))}
        </section>
      )}
      {!!body.agreements.length && (
        <section className="analysis-section">
          <h3>합의한 내용</h3>
          {body.agreements.map(fact)}
        </section>
      )}
      {!!body.open_questions.length && (
        <section className="analysis-section">
          <h3>남은 질문</h3>
          {body.open_questions.map(fact)}
        </section>
      )}
      {!!body.actions.length && (
        <section className="analysis-section">
          <h3>할 일</h3>
          {body.actions.map((action, index) => (
            <div className="analysis-fact" key={index}>
              <p>{action.text}</p>
              {action.owner_speaker_id && (
                <small>
                  {
                    transcript?.speakers.find(
                      (item) => item.id === action.owner_speaker_id,
                    )?.display_name
                  }
                </small>
              )}
              {action.due_text && <small> · {action.due_text}</small>}
              {citations(action.evidence_turn_ids)}
            </div>
          ))}
        </section>
      )}
      <p className="analysis-footnote">
        AI가 정리한 내용입니다. 근거 발언과 원본 음성으로 확인해 주세요.
      </p>
    </div>
  );
}
