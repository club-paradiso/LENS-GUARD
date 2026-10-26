import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  timeout: 60000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8765", headless: true },
  webServer: {
    command: "../.venv/bin/python -m lens_guard serve",
    url: "http://127.0.0.1:8765/api/health",
    timeout: 120000,
    reuseExistingServer: !process.env.CI,
  },
});
