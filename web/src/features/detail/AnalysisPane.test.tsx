import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { detailFixture } from "../../test/detail";
import { AnalysisPane } from "./AnalysisPane";

it("renders form sections, grouped paragraphs, unknown fields and named actions without exposing evidence by default", async () => {
  const analysis = {
    ...detailFixture.analysis!,
    body: {
      sections: [
        {
          title: "요구사항",
          groups: [
            {
              title: "파일 입력",
              paragraphs: [
                {
                  text: "음성 파일을 가져온다.",
                  evidence_sentence_ids: ["t1"],
                },
                {
                  text: "<img src=x onerror=alert(1)>",
                  evidence_sentence_ids: ["t1"],
                },
              ],
            },
          ],
          comparisons: [],
          actions: [],
        },
        { title: "예산", groups: [], comparisons: [], actions: [] },
        {
          title: "후속 조치",
          groups: [],
          comparisons: [],
          actions: [
            {
              text: "샘플 확인",
              owner_text: "김 대리",
              owner_speaker_id: null,
              due_text: "다음 주",
              evidence_sentence_ids: ["t1"],
            },
          ],
        },
      ],
    },
  };
  const evidence = vi.fn();
  const view = render(
    <AnalysisPane
      analysis={analysis}
      transcript={detailFixture.transcript}
      onEvidence={evidence}
    />,
  );
  expect(
    screen
      .getAllByRole("heading", { level: 3 })
      .map((node) => node.textContent),
  ).toEqual(["요구사항", "예산", "후속 조치"]);
  expect(screen.getByText("언급 없음")).toBeVisible();
  expect(screen.getByText("김 대리")).toBeVisible();
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeVisible();
  expect(view.container.querySelector("img")).toBeNull();
  expect(
    screen.queryByRole("button", { name: "근거 문장 t1" }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "근거 보기" }));
  await userEvent.click(
    screen.getAllByRole("button", { name: "근거 문장 t1" })[0],
  );
  expect(evidence).toHaveBeenCalledWith("t1");
});

it("renders grounded option comparisons as a table", () => {
  const analysis = {
    ...detailFixture.analysis!,
    body: {
      sections: [
        {
          title: "선택지 비교",
          groups: [],
          actions: [],
          comparisons: [
            {
              option: "안 A",
              points: [
                {
                  text: "운영 비용이 낮다는 의견",
                  evidence_sentence_ids: ["t1"],
                },
              ],
            },
            {
              option: "안 B",
              points: [
                { text: "추가 검토 필요", evidence_sentence_ids: ["t1"] },
              ],
            },
          ],
        },
      ],
    },
  };
  render(
    <AnalysisPane
      analysis={analysis}
      transcript={detailFixture.transcript}
      onEvidence={() => {}}
    />,
  );
  const table = screen.getByRole("table", { name: "선택지 비교" });
  expect(within(table).getAllByRole("row")).toHaveLength(3);
  expect(within(table).getByText("안 A")).toBeVisible();
  expect(within(table).getByText("추가 검토 필요")).toBeVisible();
});
