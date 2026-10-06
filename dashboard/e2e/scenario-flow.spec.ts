import { expect, test, type Page } from "@playwright/test";

async function selectScenario(page: Page, title: string): Promise<void> {
  await page.getByRole("button", { name: new RegExp(`^${title}`) }).click();
}

async function startAndWait(page: Page, observed: "NO_CONFIRMATION" | "CONFIRMATION"): Promise<void> {
  await page.getByRole("button", { name: /^Start$/ }).click();
  await expect(page.getByTestId("run-status")).toContainText("COMPLETED", { timeout: 60_000 });
  await expect(page.getByTestId("run-observed")).toHaveText(observed);
}

async function reset(page: Page): Promise<void> {
  await page.getByRole("button", { name: /^Reset$/ }).click();
  await expect(page.getByText("No scenario run selected")).toBeVisible();
}

test("complete local scenario, acknowledgement, export, and disconnect flow", async ({ page }) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type()) && message.text().includes("QuakeMesh")) {
      consoleProblems.push(message.text());
    }
  });
  page.on("pageerror", (error) => consoleProblems.push(error.message));

  await page.goto("/#scenarios");
  await expect(page.getByText(/connected/i, { exact: true })).toBeVisible();

  await selectScenario(page, "Isolated disturbance");
  await startAndWait(page, "NO_CONFIRMATION");
  await expect(page.getByText("DEVICE DIVERSITY GATE EVALUATED").last()).toBeVisible();
  await expect(page.getByText("FAILED", { exact: true }).last()).toBeVisible();
  await reset(page);

  await selectScenario(page, "Same-cell cluster");
  await startAndWait(page, "NO_CONFIRMATION");
  await expect(page.getByText("SPATIAL DIVERSITY GATE EVALUATED").last()).toBeVisible();
  await reset(page);

  await selectScenario(page, "Distributed corroboration");
  await startAndWait(page, "CONFIRMATION");
  await expect(page.getByText("FOOTPRINT COMPUTED").last()).toBeVisible();
  await expect(page.getByText("FRONTIER COMPUTED").last()).toBeVisible();
  await page.screenshot({ path: "../artifacts/e2e/distributed-scenario.png", fullPage: true });

  await page.getByRole("button", { name: "Alerts" }).click();
  const acknowledge = page.getByRole("button", { name: "Acknowledge" }).first();
  await expect(acknowledge).toBeVisible();
  await acknowledge.click();
  await expect(page.getByText("ACKNOWLEDGED", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Scenario Lab" }).click();
  await page.getByRole("button", { name: "Export evidence" }).click();
  await expect(page.getByText(/Exported to/)).toBeVisible();

  await page.route("http://127.0.0.1:8000/**", (route) => route.abort());
  await expect(page.getByText(/API disconnected/)).toBeVisible({ timeout: 12_000 });
  await expect(page.getByTestId("run-observed")).toHaveText("CONFIRMATION");
  expect(consoleProblems).toEqual([]);
});

test("supported viewports do not introduce page-level horizontal overflow", async ({ page }) => {
  await page.goto("/#overview");
  for (const viewport of [
    { width: 1280, height: 720 },
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow, `${viewport.width}x${viewport.height}`).toBe(false);
  }
  await page.screenshot({ path: "../artifacts/e2e/narrow-overview.png", fullPage: true });
});
