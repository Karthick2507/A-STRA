// ═══════════════════════════════════════════════════════════════
// preflight/healthCheck.orchestrator.ts
// ASTRA Framework — Health Check Orchestrator
// Runs all 4 analysers in sequence → generates preflight report
// Acts as Playwright globalSetup entry point
//Key highlights:
//
// safeRun() — error boundary wrapper around each analyser — one analyser crash never kills the whole preflight run
// shouldHardStop() — clean single-responsibility check: FAIL + HEALTH_CHECK=TRUE = stop, FAIL + HEALTH_CHECK=FALSE = warn + continue
// handleHardStop() — generates partial report even on hard stop — you always know what failed and why
// Summary table printed to console with box-drawing characters — clean visual at end of preflight run:
//
//   ┌─────────────────────────────────────┬──────────┬───────────┐
//   │ DOM Analyser                        │ ✅ PASS  │    842ms  │
//   │ Bearer Token Analyser               │ ✅ PASS  │   1203ms  │
//   │ Network Interceptor Analyser        │ ⚠️  WARN │   2100ms  │
//   │ Anti-Bot Analyser                   │ ✅ PASS  │    654ms  │
//   └─────────────────────────────────────┴──────────┴───────────┘
//
// export default runHealthCheck — Playwright globalSetup compatible
// require.main === module — also works as standalone npm run preflight
// Purple ASTRA banner printed at startup 🎨
// ═══════════════════════════════════════════════════════════════

import { validateEnv, ENV }              from "../utils/envLoader";
import { logger }                        from "../utils/logger";
import { generateReports, AnalyserResult } from "../utils/reportGenerator";
import { runDomAnalyser }                from "./domAnalyser";
import { runBearerTokenAnalyser }        from "./bearerTokenAnalyser";
import { runNetworkInterceptorAnalyser } from "./networkInterceptorAnalyser";
import { runAntiBotAnalyser }            from "./antiBotAnalyser";

// ═══════════════════════════════════════════════════════════════
// Orchestrator Entry Point
// Called by Playwright globalSetup + npm run preflight
// ═══════════════════════════════════════════════════════════════
async function runHealthCheck(): Promise<void> {
  // ─── Print ASTRA Banner ──────────────────────────────────────
  printBanner();

  // ─── Validate .env first ─────────────────────────────────────
  logger.divider("Environment Validation");
  const envResult = validateEnv();

  if (!envResult.valid) {
    logger.error("❌ Environment validation failed — missing required keys:");
    envResult.missingKeys.forEach((k) => logger.error(`   → ${k}`));
    logger.error("Please update your .env file and retry.");
    process.exit(1);
  }

  // Log warnings for optional keys using defaults
  envResult.warnings.forEach((w) => logger.warn(w));
  logger.info(`✅ Environment validated — ${envResult.loadedKeys.length} keys loaded`);
  logger.info(`🔧 Health Check Mode: ${ENV.HEALTH_CHECK ? "HARD STOP" : "WARN & PROCEED"}`);

  // ─── Run Analysers ───────────────────────────────────────────
  logger.divider("ASTRA Preflight Health Check");
  logger.info(`Target URL  : ${ENV.TARGET_PAGE_URL}`);
  logger.info(`Base URL    : ${ENV.BASE_URL}`);
  logger.info(`Browser     : ${ENV.BROWSER} | Headless: ${ENV.HEADLESS}`);

  const results: AnalyserResult[] = [];

  // ── 1. DOM Analyser ──────────────────────────────────────────
  const domResult = await safeRun("DOM Analyser", runDomAnalyser);
  results.push(domResult);
  if (shouldHardStop(domResult)) return handleHardStop(results);

  // ── 2. Bearer Token Analyser ─────────────────────────────────
  const tokenResult = await safeRun("Bearer Token Analyser", runBearerTokenAnalyser);
  results.push(tokenResult);
  if (shouldHardStop(tokenResult)) return handleHardStop(results);

  // ── 3. Network Interceptor Analyser ──────────────────────────
  const networkResult = await safeRun("Network Interceptor Analyser", runNetworkInterceptorAnalyser);
  results.push(networkResult);
  if (shouldHardStop(networkResult)) return handleHardStop(results);

  // ── 4. Anti-Bot Analyser ─────────────────────────────────────
  const antiBotResult = await safeRun("Anti-Bot Analyser", runAntiBotAnalyser);
  results.push(antiBotResult);
  if (shouldHardStop(antiBotResult)) return handleHardStop(results);

  // ─── Generate Final Report ───────────────────────────────────
  await finalizeReport(results);
}

// ═══════════════════════════════════════════════════════════════
// safeRun — wraps each analyser with error boundary
// Ensures one analyser crash doesn't kill the orchestrator
// ═══════════════════════════════════════════════════════════════
async function safeRun(
  name:    string,
  runner:  () => Promise<AnalyserResult>
): Promise<AnalyserResult> {
  try {
    logger.info(`\n⟳  Running: ${name}`);
    const result = await runner();
    return result;
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error);
    logger.error(`💥 ${name} crashed unexpectedly: ${errMsg}`);
    return {
      name,
      status:    "FAIL",
      duration:  0,
      details:   `Unexpected crash: ${errMsg}`,
      findings:  { error: errMsg },
      timestamp: new Date().toISOString(),
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// shouldHardStop — checks HEALTH_CHECK flag + analyser status
// ═══════════════════════════════════════════════════════════════
function shouldHardStop(result: AnalyserResult): boolean {
  if (result.status !== "FAIL") return false;
  if (!ENV.HEALTH_CHECK) {
    logger.warn(
      `⚠️  [${result.name}] FAILED — HEALTH_CHECK=FALSE → Warning only, continuing...`
    );
    return false;
  }
  return true;
}

// ═══════════════════════════════════════════════════════════════
// handleHardStop — generates partial report + exits process
// ═══════════════════════════════════════════════════════════════
async function handleHardStop(results: AnalyserResult[]): Promise<void> {
  logger.divider("HARD STOP — Health Check Failed");
  logger.error("❌ ASTRA Preflight HARD STOP triggered");
  logger.error(`   Failed analyser: ${results[results.length - 1].name}`);
  logger.error(`   Reason: ${results[results.length - 1].details}`);
  logger.error("   Fix the issue and re-run preflight before proceeding.");

  // Still generate report with partial results
  await generateReports(results);

  logger.error("\n📄 Partial preflight report generated — check reports/preflight/");
  process.exit(1);
}

// ═══════════════════════════════════════════════════════════════
// finalizeReport — generates full report + prints summary table
// ═══════════════════════════════════════════════════════════════
async function finalizeReport(results: AnalyserResult[]): Promise<void> {
  logger.divider("Preflight Summary");

  // ─── Print summary table ─────────────────────────────────────
  const statusIcon: Record<string, string> = {
    PASS: "✅",
    FAIL: "❌",
    WARN: "⚠️ ",
    SKIP: "⏭️ ",
  };

  console.log("\n");
  console.log("  ┌─────────────────────────────────────┬──────────┬──────────┐");
  console.log("  │ Analyser                            │ Status   │ Duration │");
  console.log("  ├─────────────────────────────────────┼──────────┼──────────┤");

  for (const r of results) {
    const icon     = statusIcon[r.status] ?? "  ";
    const namePad  = r.name.padEnd(35);
    const statPad  = `${icon} ${r.status}`.padEnd(8);
    const durPad   = `${r.duration}ms`.padStart(8);
    console.log(`  │ ${namePad} │ ${statPad} │ ${durPad} │`);
  }

  console.log("  └─────────────────────────────────────┴──────────┴──────────┘");

  const passed  = results.filter((r) => r.status === "PASS").length;
  const failed  = results.filter((r) => r.status === "FAIL").length;
  const warned  = results.filter((r) => r.status === "WARN").length;
  const skipped = results.filter((r) => r.status === "SKIP").length;

  console.log(`\n  Total: ${results.length} | ✅ ${passed} | ❌ ${failed} | ⚠️  ${warned} | ⏭️  ${skipped}`);

  // ─── Generate JSON + HTML reports ────────────────────────────
  const report = await generateReports(results);

  // ─── Final gate decision ──────────────────────────────────────
  console.log("\n");
  if (report.overallPass) {
    logger.info("🚀 ASTRA Preflight PASSED — Proceeding to test execution");
  } else if (!ENV.HEALTH_CHECK) {
    logger.warn("⚠️  ASTRA Preflight completed with failures — HEALTH_CHECK=FALSE → Proceeding anyway");
  } else {
    logger.error("❌ ASTRA Preflight FAILED — Test execution blocked");
    process.exit(1);
  }

  logger.info(`\n📄 Reports saved to: ${ENV.REPORT_OUTPUT_DIR}/`);
  logger.info(`   → preflightReport.json`);
  logger.info(`   → preflightReport.html`);
}

// ═══════════════════════════════════════════════════════════════
// printBanner — ASTRA startup banner
// ═══════════════════════════════════════════════════════════════
function printBanner(): void {
  console.log(`
\x1b[35m
  ╔═══════════════════════════════════════════════════════╗
  ║                                                       ║
  ║        ✦  A S T R A  F R A M E W O R K  ✦            ║
  ║                                                       ║
  ║   Autonomous A* Search Based Test &                   ║
  ║   Reporting Architecture                              ║
  ║                                                       ║
  ║   Version : 1.0.0                                     ║
  ║   Mode    : Preflight Health Check                    ║
  ║                                                       ║
  ╚═══════════════════════════════════════════════════════╝
\x1b[0m`);
}

// ═══════════════════════════════════════════════════════════════
// Export for Playwright globalSetup
// ═══════════════════════════════════════════════════════════════
export default runHealthCheck;

// ═══════════════════════════════════════════════════════════════
// Direct execution: npm run preflight
// ═══════════════════════════════════════════════════════════════
if (require.main === module) {
  runHealthCheck().catch((error) => {
    logger.error(`ASTRA Preflight crashed: ${error}`);
    process.exit(1);
  });
}