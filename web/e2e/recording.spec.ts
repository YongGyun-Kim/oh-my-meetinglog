import { test, expect } from "@playwright/test";

function wav() {
  const length = 16000 * 6 * 2;
  const buffer = Buffer.alloc(44 + length);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(length + 36, 4);
  buffer.write("WAVEfmt ", 8);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(16000, 24);
  buffer.writeUInt32LE(32000, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(length, 40);
  return buffer;
}

test("imports, edits, reanalyzes, seeks, exports and retains a conversation", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "파일 가져오기", exact: true })
    .click();
  await page.getByLabel("녹음 파일", { exact: true }).setInputFiles({
    name: "브라우저 검증.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await expect(page.getByText("대화 개요", { exact: true })).toBeVisible();
  await expect(
    page.getByText("언제 서비스를 시작할까요?", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "화자 정보", exact: true }).click();
  await page.getByLabel("화자 1 이름").fill("인터뷰어");
  await page.getByLabel("화자 1 역할").fill("질문자");
  await page.getByRole("button", { name: "저장", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "00:00 인터뷰어 발언 듣기" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "발언 수정", exact: true })
    .first()
    .click();
  await page
    .getByLabel("발언 내용", { exact: true })
    .fill("서비스는 언제 시작할까요?");
  await page.getByRole("button", { name: "수정 저장", exact: true }).click();
  await expect(page.getByText(/수정 전 전사를 바탕으로/)).toBeVisible();
  await page
    .getByRole("button", { name: "다시 분석", exact: true })
    .last()
    .click();
  await expect(page.getByText(/수정 전 전사를 바탕으로/)).not.toBeVisible();
  await page
    .getByRole("button", { name: "근거 00:02 화자 B", exact: true })
    .first()
    .click();
  await expect(page.getByTestId("turn-t2")).toHaveAttribute(
    "aria-current",
    "true",
  );
  await expect
    .poll(() =>
      page.locator("audio").evaluate((element) => element.currentTime),
    )
    .toBeCloseTo(2.2, 1);
  await page.getByText("내보내기", { exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("link", { name: "JSON · AI 분석용", exact: true })
    .click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.json$/);
  const path = page.url();
  await page.reload();
  await expect(
    page.getByText("서비스는 언제 시작할까요?", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "00:00 인터뷰어 발언 듣기" }),
  ).toBeVisible();
  for (const size of [
    { width: 1440, height: 900 },
    { width: 1280, height: 800 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.goto(path);
});

test("captures fake microphone audio and finalizes before processing", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "녹음 시작", exact: true }).click();
  await expect(page.getByText("00:01", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "녹음 종료", exact: true }).click();
  await expect(page.getByText("대화 개요", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "화자 정보", exact: true }),
  ).toBeVisible();
  const id = page.url().split("#record/")[1];
  const result = await page.request.get(`/api/recordings/${id}`);
  const detail = await result.json();
  expect(detail.recording.source).toBe("microphone");
  expect(detail.recording.input_state).toBe("ready");
  expect(detail.job.state).toBe("succeeded");
});
