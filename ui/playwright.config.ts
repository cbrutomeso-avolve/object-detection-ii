import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  use: {
    baseURL: "http://localhost:3000",
  },
  webServer: {
    // Windows: npm is a .ps1 script, so invoke via node directly
    command: "node node_modules/next/dist/bin/next dev",
    port: 3000,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
