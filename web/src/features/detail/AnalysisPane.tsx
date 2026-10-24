import { useState } from "react";
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
  const [showEvidence, setShowEvidence] = useState(false);
  const sentences = new Set(
    transcript?.turns.flatMap((turn) =>
      turn.sentences.map((sentence) => sentence.id),
    ),
  );
  const citations = (ids: string[]) =>
    showEvidence && (
      <span className="citations">
        {ids.map((id, index) => {
          return sentences.has(id) ? (
            <button
              key={id}
              aria-label={`근거 문장 ${id}`}
              onClick={() => onEvidence(id)}
            >
              근거 {index + 1}
            </button>
          ) : null;
        })}
      </span>
    );
  const fact = (item: Fact, index: number) => (
    <div className="analysis-fact" key={index}>
      <p>{item.text}</p>
      {citations(item.evidence_sentence_ids)}
    </div>
  );
  if ("sections" in body) {
    return (
      <div className="analysis-scroll">
        <div className="analysis-options">
          <button
            className="text-button"
            aria-pressed={showEvidence}
            onClick={() => setShowEvidence((visible) => !visible)}
          >
            {showEvidence ? "근거 숨기기" : "근거 보기"}
          </button>
        </div>
        {body.sections.map((section, index) => {
          const groups = section.groups ?? [];
          const comparisons = section.comparisons ?? [];
          const actions = section.actions ?? [];
          return (
            <section
              className="analysis-section"
              key={`${section.title}-${index}`}
            >
              <h3>{section.title}</h3>
              {!groups.length && !comparisons.length && !actions.length && (
                <p className="muted">언급 없음</p>
              )}
              {groups.map((group, groupIndex) => (
                <article className="topic" key={groupIndex}>
                  {group.title && <h4>{group.title}</h4>}
                  <div className="analysis-paragraph">
                    {group.paragraphs.map(fact)}
                  </div>
                </article>
              ))}
              {!!comparisons.length && (
                <div className="analysis-table-scroll">
                  <table className="analysis-table" aria-label={section.title}>
                    <thead>
                      <tr>
                        <th scope="col">선택지</th>
                        <th scope="col">검토 내용</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparisons.map((choice, choiceIndex) => (
                        <tr key={choiceIndex}>
                          <th scope="row">{choice.option}</th>
                          <td>{choice.points.map(fact)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {actions.map((action, actionIndex) => {
                const owner =
                  action.owner_text ??
                  transcript?.speakers.find(
                    (speaker) => speaker.id === action.owner_speaker_id,
                  )?.display_name;
                return (
                  <div className="analysis-fact" key={actionIndex}>
                    <p>{action.text}</p>
                    {owner && <small>{owner}</small>}
                    {action.due_text && (
                      <small>
                        {owner ? " · " : ""}
                        {action.due_text}
                      </small>
                    )}
                    {citations(action.evidence_sentence_ids)}
                  </div>
                );
              })}
            </section>
          );
        })}
        <p className="analysis-footnote">
          AI가 정리한 내용이에요. 필요한 내용은 원본과 확인해 주세요.
        </p>
      </div>
    );
  }
  const kind = {
    interview: "인터뷰",
    counseling: "상담",
    conversation: "대화",
    unknown: "대화 유형 미확인",
  }[body.overview.kind];
  return (
    <div className="analysis-scroll">
      <div className="analysis-options">
        <button
          className="text-button"
          aria-pressed={showEvidence}
          onClick={() => setShowEvidence((visible) => !visible)}
        >
          {showEvidence ? "근거 숨기기" : "근거 보기"}
        </button>
      </div>
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
              </div>
              <div className="analysis-paragraph">
                {topic.discussion.map(fact)}
              </div>
              {!!topic.different_views.length && (
                <div className="different-views">
                  <h5>서로 다른 의견</h5>
                  <div className="analysis-paragraph">
                    {topic.different_views.map(fact)}
                  </div>
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
              {citations(action.evidence_sentence_ids)}
            </div>
          ))}
        </section>
      )}
      <p className="analysis-footnote">
        AI가 정리한 내용이에요. 필요한 내용은 원본과 확인해 주세요.
      </p>
    </div>
  );
}
