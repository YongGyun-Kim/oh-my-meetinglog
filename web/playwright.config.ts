import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  use: {
    baseURL: "http://127.0.0.1:5174",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    launchOptions: {
      args: [
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
      ],
    },
  },
  webServer: [
    {
      command: "uv run --no-sync python -m tests.e2e_server",
      cwd: "..",
      url: "http://127.0.0.1:8766/api/health",
      reuseExistingServer: false,
      timeout: 20_000,
    },
    {
      command: "npm run dev -- --port 5174",
      env: { MEETINGLOG_API_URL: "http://127.0.0.1:8766" },
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
      timeout: 20_000,
    },
  ],
});
