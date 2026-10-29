import { defineConfig } from "@playwright/test";
import path from "node:path";
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
    // Do not depend on the editable-install .pth file, which macOS can mark hidden.
    env: { PYTHONPATH: path.resolve("../src") },
  },
});
