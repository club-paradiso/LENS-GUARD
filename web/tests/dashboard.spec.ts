import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync, mkdirSync } from "node:fs";
import path from "node:path";
const root = path.resolve("..");
const artifact = path.join(root, "work", "e2e-synthetic.pcap");
test.beforeAll(() => {
  mkdirSync(path.dirname(artifact), { recursive: true });
  execFileSync(
    path.join(root, ".venv/bin/python"),
    ["-m", "lens_guard", "fixture", artifact],
    { cwd: root },
  );
});

test("demo, selection, replay, research and export", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page).toHaveTitle(/LENS-GUARD/);
  await expect(
    page.getByRole("heading", { name: "Traffic observatory" }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("SIMULATED DATA");
  await expect(
    page.getByRole("button", { name: "Select source 5" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Select source 5" }).click();
  await expect(
    page.getByText("Experimental score · not a probability"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Replay", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export report" }).click();
  const dl = await downloadPromise;
  const file = await dl.path();
  const report = JSON.parse(readFileSync(file!, "utf8"));
  expect(report.provenance).toBe("synthetic_demo");
  expect(report.simulation.physical_devices).toBe(0);
  await page
    .getByRole("button", { name: "Research notes", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Explainable baseline" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("pcap authorization, success, provenance and invalid file", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "PCAP file", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Analyze locally" }),
  ).toBeDisabled();
  await page.getByLabel("PCAP / PCAPNG file").setInputFiles(artifact);
  await page
    .getByLabel("Authorized source MAC addresses")
    .fill("02:00:00:00:00:01");
  await page.getByLabel("Data origin").selectOption("synthetic_file");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Analyze locally" }).click();
  await expect(page.getByRole("status")).toContainText("SYNTHETIC FILE");
  await expect(
    page.getByRole("button", { name: "Select source 1" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Candidate");
  await page
    .getByLabel("PCAP / PCAPNG file")
    .setInputFiles({
      name: "invalid.pcap",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("invalid"),
    });
  await page.getByRole("button", { name: "Analyze locally" }).click();
  await expect(page.getByRole("alert")).toContainText("header");
  await expect(
    page.getByRole("button", { name: "Export report" }),
  ).toBeDisabled();
});

test("desktop and mobile layout, screenshot evidence", async ({ page }) => {
  await page.setViewportSize({ width: 1505, height: 1045 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Select source 5" }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(root, "docs/dashboard-desktop.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "PCAP file", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(root, "docs/dashboard-mobile.png"),
    fullPage: true,
  });
});

test("mode switching cannot retain stale synthetic results", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "PCAP file", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("OFFLINE ANALYSIS");
  await expect(
    page.getByRole("button", { name: "Export report" }),
  ).toBeDisabled();
});

test("simulation updates engine results over time", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Select source 5" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Run simulation", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Stop simulation", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Analysis summary")).toContainText("10 s");
  await expect(page.getByLabel("Analysis summary")).toContainText("11 s", {
    timeout: 15000,
  });
  await page
    .getByRole("button", { name: "Stop simulation", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("SIMULATED DATA");
});
