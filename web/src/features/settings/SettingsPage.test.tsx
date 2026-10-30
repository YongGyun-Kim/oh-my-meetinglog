import { render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { SettingsPage } from "./SettingsPage";

it("shows installation commands for missing models and links to the configured downloads", async () => {
  vi.spyOn(api, "settings").mockResolvedValue({
    mode: "local_only",
    api_configured: false,
    media_tools_ready: false,
    engines: [
      {
        name: "asr",
        repo_id: "mlx-community/Qwen3-ASR-1.7B-8bit",
        ready: true,
        quality: "unverified",
      },
      {
        name: "vad",
        repo_id: "mlx-community/silero-vad",
        ready: false,
        quality: "unverified",
      },
      {
        name: "analysis",
        repo_id: "qwen3:8b",
        ready: false,
        quality: "unverified",
      },
    ],
  });
  vi.spyOn(api, "cliConnections").mockResolvedValue([]);
  render(<SettingsPage />);
  const vad = await screen.findByRole("group", { name: "음성 구간 탐지" });
  expect(
    within(vad).getByText(
      "uv run --extra speech meetinglog prepare-models --models vad",
    ),
  ).toBeVisible();
  expect(within(vad).getByRole("link")).toHaveAttribute(
    "href",
    "https://huggingface.co/mlx-community/silero-vad",
  );
  const asr = screen.getByRole("group", { name: "한국어 전사" });
  expect(within(asr).queryByText(/prepare-models/)).not.toBeInTheDocument();
  const analysis = screen.getByRole("group", { name: "대화 분석" });
  expect(within(analysis).getByText("ollama pull qwen3:8b")).toBeVisible();
  expect(
    within(analysis).getByRole("link", { name: "qwen3:8b" }),
  ).toHaveAttribute("href", "https://ollama.com/library/qwen3");
  expect(screen.getByText("brew install ffmpeg")).toBeVisible();
});
