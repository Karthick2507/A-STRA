// ═══════════════════════════════════════════════════════════════
// playwright.config.ts
// ASTRA Framework — Playwright Configuration
// Autonomous A* Search Based Test & Reporting Architecture
//Key highlights:
//
// globalSetup → points to healthCheck.orchestrator.ts — preflight runs automatically before any test
// fullyParallel: false + workers: 1 — intentional, A* feedback loop requires sequential execution to learn from each attempt
// BEARER_TOKEN auto-injected into extraHTTPHeaders — every Playwright request carries auth automatically
// trace: "on-first-retry" + screenshot: "only-on-failure" + video: "on-first-retry" — full debug capture on failures
// browserDeviceMap — switching browsers is just changing BROWSER=firefox in .env, zero code change
// Cross-browser matrix pre-wired but commented — ready to uncomment for CI runs
// ═══════════════════════════════════════════════════════════════

import { defineConfig, devices } from "@playwright/test";
import * as dotenv from "dotenv";
import * as path from "path";

// ─── Load .env ──────────────────────────────────────────────────
dotenv.config({ path: path.resolve(__dirname, ".env") });

// ─── Env Helpers ────────────────────────────────────────────────
const BASE_URL        = process.env.BASE_URL         || "http://localhost:3000";
const HEADLESS        = process.env.HEADLESS          !== "false";
const SLOW_MO         = parseInt(process.env.SLOW_MO  || "0", 10);
const BROWSER         = process.env.BROWSER           || "chromium";
const VIEWPORT_WIDTH  = parseInt(process.env.VIEWPORT_WIDTH  || "1280", 10);
const VIEWPORT_HEIGHT = parseInt(process.env.VIEWPORT_HEIGHT || "720",  10);
const REPORT_DIR      = process.env.TEST_REPORT_DIR   || "reports/testResults";

// ─── Browser Device Map ─────────────────────────────────────────
const browserDeviceMap: Record<string, typeof devices[string]> = {
  chromium: devices["Desktop Chrome"],
  firefox:  devices["Desktop Firefox"],
  webkit:   devices["Desktop Safari"],
};

const selectedDevice = browserDeviceMap[BROWSER] ?? devices["Desktop Chrome"];

// ═══════════════════════════════════════════════════════════════
export default defineConfig({

  // ─── Test Discovery ───────────────────────────────────────────
  testDir:  "./runners",
  testMatch: "**/*.runner.ts",           // Only pick up runner files

  // ─── Parallelism ──────────────────────────────────────────────
  fullyParallel: false,                  // Sequential by default (A* feedback loop)
  workers: 1,                            // Single worker — maintains A* state

  // ─── Retry Strategy ───────────────────────────────────────────
  retries: parseInt(process.env.API_RETRY_COUNT || "3", 10),
  timeout: parseInt(process.env.ASTAR_GOAL_TIMEOUT || "30000", 10),

  // ─── Reporting ────────────────────────────────────────────────
  reporter: [
    ["list"],                            // Console output
    ["json",  { outputFile: `${REPORT_DIR}/uiTestReport.json` }],
    ["html",  {
      outputFolder: `${REPORT_DIR}`,
      open: "never",                     // Don't auto-open browser
    }],
  ],

  // ─── Global Setup ─────────────────────────────────────────────
  globalSetup:    "./preflight/healthCheck.orchestrator.ts",

  // ─── Shared Settings ──────────────────────────────────────────
  use: {
    baseURL:           BASE_URL,
    headless:          HEADLESS,
    slowMo:            SLOW_MO,
    viewport:          { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },

    // ─── Tracing & Debugging ──────────────────────────────────
    trace:             "on-first-retry",  // Capture trace on retry
    screenshot:        "only-on-failure", // Screenshot on failure
    video:             "on-first-retry",  // Video on retry

    // ─── Network ──────────────────────────────────────────────
    ignoreHTTPSErrors: true,              // Handle self-signed certs
    extraHTTPHeaders: {
      Authorization: process.env.BEARER_TOKEN
        ? `${process.env.TOKEN_TYPE} ${process.env.BEARER_TOKEN}`
        : "",
    },

    // ─── Timeouts ─────────────────────────────────────────────
    actionTimeout:     15000,             // Per action timeout
    navigationTimeout: 30000,             // Page navigation timeout
  },

  // ─── Projects (Browser Matrix) ────────────────────────────────
  projects: [
    {
      name:  BROWSER,
      use:   { ...selectedDevice },
    },

    // Uncomment below to run cross-browser in CI
    // {
    //   name: "firefox",
    //   use: { ...devices["Desktop Firefox"] },
    // },
    // {
    //   name: "webkit",
    //   use: { ...devices["Desktop Safari"] },
    // },
  ],

  // ─── Output Directories ───────────────────────────────────────
  outputDir: `${REPORT_DIR}/artifacts`,   // Screenshots, videos, traces

  // ─── Expect Config ────────────────────────────────────────────
  expect: {
    timeout: 10000,                        // Assertion timeout
    toMatchSnapshot: {
      maxDiffPixels: 100,                  // Visual comparison tolerance
    },
  },
});