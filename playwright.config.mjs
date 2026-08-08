import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:4173",
    viewport: { width: 390, height: 844 },
    // Chromium's mobile emulation uses a wider layout viewport than the 390px
    // visual viewport here, which puts fixed header controls off-screen.
    // Narrow viewport + touch is sufficient for this responsive regression.
    isMobile: false,
    hasTouch: true,
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  webServer: {
    command: process.platform === "win32"
      ? "py -3 -m http.server 4173 --bind 127.0.0.1"
      : "python3 -m http.server 4173 --bind 127.0.0.1",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
