// ═══════════════════════════════════════════════════════════════
// runners/e2e/e2eTestRunner.ts
// ASTRA Framework — E2E Integration Test Runner
// Orchestrates full pipeline: Preflight → UI → API → Report
// This is the master runner — npm run full:run calls this
// ═══════════════════════════════════════════════════════════════
//Key highlights — the master orchestrator:
// 5-Phase pipeline:
// Phase 1 → Preflight (DOM + Token + Network + AntiBot)
// Phase 2 → Auto Schema Build from preflight output
// Phase 3 → UI Test Execution
// Phase 4 → API Test Execution
// Phase 5 → Master E2E Report (JSON + HTML)
//
// E2ERunOptions — 4 CLI skip flags supported: --skip-preflight, --skip-ui, --skip-api, --skip-schema — flexible for CI pipelines
// HEALTH_CHECK=TRUE hard stop respected — Phase 1 failure aborts entire run immediately
// existingSchemasAvailable() — graceful fallback — if schema build fails, uses last-known good schemas
// buildE2EHtml() — master dark HTML report with pass rate %, 4-phase status table, duration
// Each phase wrapped in try/catch — one phase crash never kills the entire run
// printFinalSummary() — clean box-drawing summary table at end of every run:
//
//   ┌────────────────────────────────────────────┐
//   │  Overall Status  : ✅ PASSED               │
//   │  Preflight       : PASS                    │
//   │  Total Tests     : 12                      │
//   │  Passed          : 11                      │
//   │  Failed          : 1                       │
//   │  Duration        : 47.3s                   │
//   └────────────────────────────────────────────┘

import * as fs       from "fs-extra";
import * as path     from "path";
import { ENV }       from "../../utils/envLoader";
import { logger }    from "../../utils/logger";
import { UiTestRunner, UiRunResult }    from "../ui/uiTestRunner";
import { ApiTestRunner, ApiRunResult }  from "../api/apiTestRunner";
import { buildSchemasFromPreflight }    from "../../core/schemaBuilder";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export interface E2ERunResult {
  success:         boolean;
  preflight:       "PASS" | "FAIL" | "WARN" | "SKIP";
  schemaBuilt:     boolean;
  ui:              UiRunResult  | null;
  api:             ApiRunResult | null;
  totalTests:      number;
  totalPassed:     number;
  totalFailed:     number;
  duration:        number;
  reportPath:      string;
  timestamp:       string;
}

export interface E2ERunOptions {
  skipPreflight?:  boolean;     // Skip preflight (use existing schema)
  skipUi?:         boolean;     // Skip UI tests
  skipApi?:        boolean;     // Skip API tests
  skipSchemaGen?:  boolean;     // Skip schema build (use existing)
}

// ═══════════════════════════════════════════════════════════════
// E2ETestRunner
// ═══════════════════════════════════════════════════════════════
export class E2ETestRunner {

  private readonly reportDir: string;

  constructor() {
    this.reportDir = path.resolve(__dirname, "../../", ENV.TEST_REPORT_DIR);
  }

  // ═══════════════════════════════════════════════════════════
  // run — master pipeline
  // ═══════════════════════════════════════════════════════════
  async run(options: E2ERunOptions = {}): Promise<E2ERunResult> {
    const startTime = Date.now();
    const timestamp = new Date().toISOString();

    this.printMasterBanner();
    await fs.ensureDir(this.reportDir);

    const result: E2ERunResult = {
      success:     false,
      preflight:   "SKIP",
      schemaBuilt: false,
      ui:          null,
      api:         null,
      totalTests:  0,
      totalPassed: 0,
      totalFailed: 0,
      duration:    0,
      reportPath:  path.join(this.reportDir, "index.html"),
      timestamp,
    };

    // ══════════════════════════════════════════════════════════
    // PHASE 1 — Preflight Health Check
    // ══════════════════════════════════════════════════════════
    if (!options.skipPreflight) {
      logger.divider("Phase 1 — Preflight Health Check");
      const preflightStatus = await this.runPreflight();
      result.preflight = preflightStatus;

      if (preflightStatus === "FAIL" && ENV.HEALTH_CHECK) {
        logger.error("❌ E2E Run aborted — Preflight HARD STOP");
        result.duration = Date.now() - startTime;
        await this.saveE2EReport(result);
        return result;
      }

      if (preflightStatus === "FAIL") {
        logger.warn("⚠️  Preflight failed — HEALTH_CHECK=FALSE → continuing");
      }

    } else {
      logger.info("⏭️  Preflight skipped via options.skipPreflight");
      result.preflight = "SKIP";
    }

    // ══════════════════════════════════════════════════════════
    // PHASE 2 — Schema Build
    // ══════════════════════════════════════════════════════════
    if (!options.skipSchemaGen) {
      logger.divider("Phase 2 — Auto Schema Build");

      try {
        const schemaOutput = await buildSchemasFromPreflight();
        result.schemaBuilt = !!(schemaOutput.uiSchema || schemaOutput.apiSchema);

        if (result.schemaBuilt) {
          logger.info("✅ Schemas built from preflight output");
          if (schemaOutput.savedTo.ui)  logger.info(`   UI  → ${schemaOutput.savedTo.ui}`);
          if (schemaOutput.savedTo.api) logger.info(`   API → ${schemaOutput.savedTo.api}`);
        } else {
          logger.warn("⚠️  Schema build produced no output — using existing schemas");
          result.schemaBuilt = await this.existingSchemasAvailable();
        }

      } catch (err) {
        logger.error(`Schema build failed: ${err}`);
        logger.warn("Attempting to use existing schemas...");
        result.schemaBuilt = await this.existingSchemasAvailable();
      }

    } else {
      logger.info("⏭️  Schema build skipped — using existing schemas");
      result.schemaBuilt = await this.existingSchemasAvailable();
    }

    if (!result.schemaBuilt) {
      logger.error("❌ No schemas available — cannot run tests");
      result.duration = Date.now() - startTime;
      await this.saveE2EReport(result);
      return result;
    }

    // ══════════════════════════════════════════════════════════
    // PHASE 3 — UI Tests
    // ══════════════════════════════════════════════════════════
    if (!options.skipUi) {
      logger.divider("Phase 3 — UI Test Execution");

      try {
        const uiRunner = new UiTestRunner();
        result.ui      = await uiRunner.run();

        result.totalTests  += result.ui.testsGenerated;
        result.totalPassed += result.ui.testsPassed;
        result.totalFailed += result.ui.testsFailed;

        logger.info(
          `UI Tests: ${result.ui.testsPassed} passed, ${result.ui.testsFailed} failed`
        );

      } catch (err) {
        logger.error(`UI runner crashed: ${err}`);
        result.ui = {
          success: false, testsGenerated: 0,
          testsPassed: 0, testsFailed: 0,
          duration: 0, reportPath: "",
        };
      }

    } else {
      logger.info("⏭️  UI tests skipped via options.skipUi");
    }

    // ══════════════════════════════════════════════════════════
    // PHASE 4 — API Tests
    // ══════════════════════════════════════════════════════════
    if (!options.skipApi) {
      logger.divider("Phase 4 — API Test Execution");

      try {
        const apiRunner = new ApiTestRunner();
        result.api      = await apiRunner.run();

        result.totalTests  += result.api.testsGenerated;
        result.totalPassed += result.api.testsPassed;
        result.totalFailed += result.api.testsFailed;

        logger.info(
          `API Tests: ${result.api.testsPassed} passed, ${result.api.testsFailed} failed | ` +
          `Endpoints: ${result.api.endpointsCovered}`
        );

      } catch (err) {
        logger.error(`API runner crashed: ${err}`);
        result.api = {
          success: false, testsGenerated: 0,
          testsPassed: 0, testsFailed: 0,
          endpointsCovered: 0, duration: 0, reportPath: "",
        };
      }

    } else {
      logger.info("⏭️  API tests skipped via options.skipApi");
    }

    // ══════════════════════════════════════════════════════════
    // PHASE 5 — Final Report
    // ══════════════════════════════════════════════════════════
    result.success  = result.totalFailed === 0 &&
                      (result.ui?.success !== false) &&
                      (result.api?.success !== false);
    result.duration = Date.now() - startTime;

    await this.saveE2EReport(result);
    this.printFinalSummary(result);

    return result;
  }

  // ═══════════════════════════════════════════════════════════
  // runPreflight — invokes health check orchestrator
  // ═══════════════════════════════════════════════════════════
  private async runPreflight(): Promise<"PASS" | "FAIL" | "WARN"> {
    try {
      const { default: runHealthCheck } = await import(
        "../../preflight/healthCheck.orchestrator"
      );
      await runHealthCheck();
      return "PASS";
    } catch (err: any) {
      if (err?.code === "PREFLIGHT_HARD_STOP") return "FAIL";
      logger.warn(`Preflight warning: ${err?.message ?? err}`);
      return "WARN";
    }
  }

  // ═══════════════════════════════════════════════════════════
  // existingSchemasAvailable
  // ═══════════════════════════════════════════════════════════
  private async existingSchemasAvailable(): Promise<boolean> {
    const uiSchema  = path.resolve(__dirname, "../../schemas/ui/autoGeneratedSchema.json");
    const apiSchema = path.resolve(__dirname, "../../schemas/api/autoGeneratedSchema.json");

    const uiExists  = await fs.pathExists(uiSchema);
    const apiExists = await fs.pathExists(apiSchema);

    if (uiExists)  logger.info("✅ Existing UI schema found");
    if (apiExists) logger.info("✅ Existing API schema found");

    return uiExists || apiExists;
  }

  // ═══════════════════════════════════════════════════════════
  // saveE2EReport — writes master E2E JSON + HTML summary
  // ═══════════════════════════════════════════════════════════
  private async saveE2EReport(result: E2ERunResult): Promise<void> {
    await fs.ensureDir(this.reportDir);

    // ─── JSON report ─────────────────────────────────────────
    const jsonPath = path.join(this.reportDir, "e2eReport.json");
    await fs.writeJson(jsonPath, result, { spaces: 2 });

    // ─── HTML summary ─────────────────────────────────────────
    const htmlPath = path.join(this.reportDir, "e2eReport.html");
    await fs.writeFile(htmlPath, this.buildE2EHtml(result), "utf-8");

    logger.info(`📄 E2E reports saved → ${this.reportDir}`);
  }

  // ═══════════════════════════════════════════════════════════
  // buildE2EHtml — master E2E summary HTML
  // ═══════════════════════════════════════════════════════════
  private buildE2EHtml(result: E2ERunResult): string {
    const statusColor = result.success ? "#22c55e" : "#ef4444";
    const statusText  = result.success ? "✅ PASSED" : "❌ FAILED";
    const passRate    = result.totalTests > 0
      ? Math.round((result.totalPassed / result.totalTests) * 100)
      : 0;

    const phaseRow = (
      label: string,
      status: string,
      detail: string
    ) => {
      const color = status === "PASS" || status === "SKIP"
        ? "#22c55e" : status === "WARN" ? "#f59e0b" : "#ef4444";
      return `
      <tr>
        <td style="padding:12px 16px;border-top:1px solid #0f172a">${label}</td>
        <td style="padding:12px 16px;border-top:1px solid #0f172a">
          <span style="background:${color};color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600">${status}</span>
        </td>
        <td style="padding:12px 16px;border-top:1px solid #0f172a;font-size:13px;color:#94a3b8">${detail}</td>
      </tr>`;
    };

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>ASTRA — E2E Run Report</title>
  <style>
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:'Segoe UI',system-ui,sans-serif; background:#0f172a; color:#e2e8f0; padding:32px; }
    .logo { font-size:28px; font-weight:800; letter-spacing:4px; background:linear-gradient(135deg,#6366f1,#a855f7); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .status-badge { display:inline-block; padding:10px 28px; border-radius:999px; font-size:20px; font-weight:700; background:${statusColor}; color:#fff; margin:20px 0; letter-spacing:2px; }
    .cards { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin:24px 0; }
    .card { background:#1e293b; border-radius:12px; padding:20px; text-align:center; }
    .card .num { font-size:32px; font-weight:800; }
    .card .lbl { font-size:12px; color:#64748b; margin-top:4px; text-transform:uppercase; letter-spacing:1px; }
    table { width:100%; border-collapse:collapse; background:#1e293b; border-radius:12px; overflow:hidden; margin-top:24px; }
    th { background:#0f172a; padding:12px 16px; text-align:left; font-size:12px; color:#64748b; text-transform:uppercase; letter-spacing:1px; }
    .section-title { font-size:14px; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:2px; margin:24px 0 12px; }
    footer { margin-top:32px; text-align:center; font-size:12px; color:#334155; }
  </style>
</head>
<body>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid #1e293b">
    <div>
      <div class="logo">✦ ASTRA</div>
      <div style="font-size:13px;color:#475569;margin-top:4px">E2E Integration Run Report</div>
    </div>
    <div style="font-size:13px;color:#64748b;text-align:right">
      <div>${new Date(result.timestamp).toLocaleString()}</div>
      <div>Duration: ${(result.duration / 1000).toFixed(1)}s</div>
      <div>Target: ${ENV.TARGET_PAGE_URL}</div>
    </div>
  </div>

  <div class="status-badge">${statusText}</div>

  <div class="cards">
    <div class="card"><div class="num" style="color:#94a3b8">${result.totalTests}</div><div class="lbl">Total Tests</div></div>
    <div class="card"><div class="num" style="color:#22c55e">${result.totalPassed}</div><div class="lbl">Passed</div></div>
    <div class="card"><div class="num" style="color:#ef4444">${result.totalFailed}</div><div class="lbl">Failed</div></div>
    <div class="card"><div class="num" style="color:#a855f7">${passRate}%</div><div class="lbl">Pass Rate</div></div>
  </div>

  <div class="section-title">Phase Summary</div>
  <table>
    <thead><tr><th>Phase</th><th>Status</th><th>Detail</th></tr></thead>
    <tbody>
      ${phaseRow("Preflight Health Check", result.preflight, "DOM + Token + Network + AntiBot")}
      ${phaseRow("Schema Build",           result.schemaBuilt ? "PASS" : "FAIL", "Auto-generated from preflight output")}
      ${phaseRow("UI Tests",               result.ui?.success ? "PASS" : result.ui ? "FAIL" : "SKIP",
        result.ui ? `${result.ui.testsPassed} passed / ${result.ui.testsFailed} failed (${result.ui.duration}ms)` : "Skipped")}
      ${phaseRow("API Tests",              result.api?.success ? "PASS" : result.api ? "FAIL" : "SKIP",
        result.api ? `${result.api.testsPassed} passed / ${result.api.testsFailed} failed | ${result.api.endpointsCovered} endpoints` : "Skipped")}
    </tbody>
  </table>

  <footer>ASTRA Framework v${ENV.FRAMEWORK_VERSION} — Auto-generated E2E Run Report</footer>
</body>
</html>`;
  }

  // ═══════════════════════════════════════════════════════════
  // printFinalSummary
  // ═══════════════════════════════════════════════════════════
  private printFinalSummary(result: E2ERunResult): void {
    logger.divider("ASTRA — E2E Run Complete");
    console.log(`
  ┌─────────────────────────────────────────────────────┐
  │           ASTRA E2E RUN SUMMARY                     │
  ├─────────────────────────────────────────────────────┤
  │  Overall Status  : ${result.success ? "✅ PASSED" : "❌ FAILED"}                        │
  │  Preflight       : ${result.preflight.padEnd(4)}                                 │
  │  Schema Built    : ${result.schemaBuilt ? "YES " : "NO  "}                                 │
  │  Total Tests     : ${String(result.totalTests).padEnd(4)}                                 │
  │  Passed          : ${String(result.totalPassed).padEnd(4)}                                 │
  │  Failed          : ${String(result.totalFailed).padEnd(4)}                                 │
  │  Duration        : ${(result.duration / 1000).toFixed(1)}s                               │
  │  Report          : ${ENV.TEST_REPORT_DIR}/e2eReport.html     │
  └─────────────────────────────────────────────────────┘
    `);
  }

  // ═══════════════════════════════════════════════════════════
  // printMasterBanner
  // ═══════════════════════════════════════════════════════════
  private printMasterBanner(): void {
    console.log(`
\x1b[35m
  ╔═══════════════════════════════════════════════════════╗
  ║                                                       ║
  ║        ✦  A S T R A  —  E 2 E  R U N N E R  ✦        ║
  ║                                                       ║
  ║   Phase 1 : Preflight Health Check                    ║
  ║   Phase 2 : Auto Schema Build                         ║
  ║   Phase 3 : UI Test Execution                         ║
  ║   Phase 4 : API Test Execution                        ║
  ║   Phase 5 : Master Report Generation                  ║
  ║                                                       ║
  ╚═══════════════════════════════════════════════════════╝
\x1b[0m`);
  }
}

// ═══════════════════════════════════════════════════════════════
// Direct execution: npm run test:e2e
// ═══════════════════════════════════════════════════════════════
async function main(): Promise<void> {
  const runner = new E2ETestRunner();

  // ─── Parse CLI flags ──────────────────────────────────────
  const args = process.argv.slice(2);
  const options: E2ERunOptions = {
    skipPreflight: args.includes("--skip-preflight"),
    skipUi:        args.includes("--skip-ui"),
    skipApi:       args.includes("--skip-api"),
    skipSchemaGen: args.includes("--skip-schema"),
  };

  if (Object.values(options).some(Boolean)) {
    logger.info(`E2E options: ${JSON.stringify(options)}`);
  }

  const result = await runner.run(options);
  process.exit(result.success ? 0 : 1);
}

if (require.main === module) {
  main().catch((err) => {
    logger.error(`E2E runner crashed: ${err}`);
    process.exit(1);
  });
}