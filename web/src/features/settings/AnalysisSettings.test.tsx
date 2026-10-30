import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { AnalysisSettings } from "./AnalysisSettings";

const catalog = [
  {
    id: "alpha",
    name: "Connected Alpha",
    reasoning: ["low", "high"],
    default_reasoning: "low",
    aliases: [],
  },
  {
    id: "beta",
    name: "Connected Beta",
    reasoning: ["medium"],
    default_reasoning: "medium",
    aliases: [],
  },
];
const choices = {
  models: ["alpha", "beta"],
  catalog,
  default_model: "alpha",
  reasoning: ["default", "low", "high"],
  message: null,
};
afterEach(() => vi.restoreAllMocks());

it("selects discovered models and shows only that model reasoning levels", async () => {
  let stored = { provider: "codex", model: "alpha", reasoning: "high" };
  vi.spyOn(api, "analysisSettings").mockImplementation(
    async () => stored as never,
  );
  vi.spyOn(api, "analysisOptions").mockResolvedValue(choices);
  vi.spyOn(api, "saveAnalysisSettings").mockImplementation(async (body) => {
    stored = body;
    return body;
  });
  const user = userEvent.setup();
  const view = render(<AnalysisSettings refreshCount={0} />);
  await screen.findByRole("option", { name: "Connected Beta" });
  await user.selectOptions(
    screen.getByRole("combobox", { name: "모델" }),
    "beta",
  );
  expect(screen.getByLabelText("추론 수준")).toHaveValue("default");
  expect(
    within(screen.getByLabelText("추론 수준")).queryByRole("option", {
      name: "높음",
    }),
  ).toBeNull();
  await user.selectOptions(screen.getByLabelText("추론 수준"), "medium");
  expect(stored.model).toBe("alpha");
  await user.click(screen.getByRole("button", { name: "저장" }));
  expect(await screen.findByRole("status")).toHaveTextContent("저장했어요");
  view.unmount();
  render(<AnalysisSettings refreshCount={0} />);
  await screen.findByRole("option", { name: "Connected Beta" });
  await waitFor(() =>
    expect(screen.getByLabelText("모델")).toHaveValue("beta"),
  );
  expect(screen.getByLabelText("추론 수준")).toHaveValue("medium");
});

it("keeps settings after failed save and lets the user retry", async () => {
  vi.spyOn(api, "analysisSettings").mockResolvedValue({
    provider: "claude",
    model: "alpha",
    reasoning: "default",
  });
  vi.spyOn(api, "analysisOptions").mockResolvedValue(choices);
  vi.spyOn(api, "saveAnalysisSettings").mockRejectedValue(
    new Error("저장에 실패했어요."),
  );
  render(<AnalysisSettings refreshCount={0} />);
  const user = userEvent.setup();
  await screen.findByRole("option", { name: "Connected Alpha" });
  await user.selectOptions(screen.getByLabelText("추론 수준"), "high");
  await user.click(screen.getByRole("button", { name: "저장" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("저장에 실패");
  expect(screen.getByLabelText("모델")).toHaveValue("alpha");
  expect(screen.getByLabelText("추론 수준")).toHaveValue("high");
  expect(screen.getByRole("button", { name: "저장" })).toBeEnabled();
});

it("does not treat unavailable saved reasoning as a supported option", async () => {
  vi.spyOn(api, "analysisSettings").mockResolvedValue({
    provider: "codex",
    model: "beta",
    reasoning: "high",
  });
  vi.spyOn(api, "analysisOptions").mockResolvedValue(choices);
  render(<AnalysisSettings refreshCount={0} />);
  await screen.findByRole("option", { name: "Connected Beta" });
  expect(screen.getByText(/저장된 추론 수준/)).toBeVisible();
  expect(
    within(screen.getByLabelText("추론 수준")).queryByRole("option", {
      name: "높음",
    }),
  ).toBeNull();
  expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
});

it("offers only default reasoning when login or catalog discovery fails", async () => {
  vi.spyOn(api, "analysisSettings").mockResolvedValue({
    provider: "claude",
    model: "",
    reasoning: "default",
  });
  vi.spyOn(api, "analysisOptions").mockResolvedValue({
    models: [],
    catalog: [],
    default_model: "",
    reasoning: ["default"],
    message: "로그인해 주세요.",
  });
  render(<AnalysisSettings refreshCount={0} />);
  expect(await screen.findByText("로그인해 주세요.")).toBeVisible();
  expect(screen.getByLabelText("모델")).toHaveAttribute("type", "text");
  expect(
    within(screen.getByLabelText("추론 수준")).getAllByRole("option"),
  ).toHaveLength(1);
});

it("ignores a slow catalog after changing providers", async () => {
  let finish: ((value: typeof choices) => void) | undefined;
  vi.spyOn(api, "analysisSettings").mockResolvedValue({
    provider: "codex",
    model: "alpha",
    reasoning: "default",
  });
  vi.spyOn(api, "analysisOptions").mockImplementation(async (provider) =>
    provider === "codex"
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : {
          ...choices,
          models: ["claude-live"],
          catalog: [
            {
              id: "claude-live",
              name: "Claude connected",
              reasoning: ["medium"],
              default_reasoning: null,
              aliases: [],
            },
          ],
          default_model: "claude-live",
        },
  );
  render(<AnalysisSettings refreshCount={0} />);
  await waitFor(() => expect(finish).toBeDefined());
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("분석 도구"), "claude");
  await screen.findByRole("option", { name: "Claude connected" });
  finish!(choices);
  await waitFor(() =>
    expect(
      screen.queryByRole("option", { name: "Connected Alpha" }),
    ).toBeNull(),
  );
  await user.selectOptions(screen.getByLabelText("모델"), "claude-live");
  expect(
    within(screen.getByLabelText("추론 수준")).queryByRole("option", {
      name: "높음",
    }),
  ).toBeNull();
});
