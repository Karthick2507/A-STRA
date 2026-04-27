// ═══════════════════════════════════════════════════════════════
// utils/reportGenerator.ts
// ASTRA Framework — JSON + HTML Preflight Report Generator
//Key highlights:
//
// buildReport() — assembles full PreflightReport object from all 4 analyser results
// generateReports() — single entry point, respects REPORT_FORMAT=json|html|both from .env
// HTML Report is dark-themed, professional grade with:
//
// 🎯 Gate Status badge (color coded green/red/amber)
// Summary cards — Total / Passed / Failed / Warned / Skipped
// Per-analyser table with findings JSON inline
// Config panel showing URLs + health check mode
//
//
// statusColor + statusIcon maps — consistent visual language across report and logs
// gateStatus logic — FAIL if any analyser failed, WARN if warnings exist, PASS if all clean
// ═══════════════════════════════════════════════════════════════

import * as fs from "fs-extra";
import * as path from "path";
import { ENV } from "./envLoader";
import { logger } from "./logger";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export type AnalyserStatus = "PASS" | "FAIL" | "WARN" | "SKIP";
export type GateStatus     = "PASS" | "FAIL" | "WARN";

export interface AnalyserResult {
  name:       string;
  status:     AnalyserStatus;
  duration:   number;           // ms
  details:    string;
  findings:   Record<string, unknown>;
  timestamp:  string;
}

export interface PreflightReport {
  framework:    string;
  version:      string;
  generatedAt:  string;
  baseUrl:      string;
  targetUrl:    string;
  healthCheck:  boolean;        // TRUE = hard stop mode
  gateStatus:   GateStatus;
  overallPass:  boolean;
  analysers:    AnalyserResult[];
  summary:      {
    total:    number;
    passed:   number;
    failed:   number;
    warned:   number;
    skipped:  number;
  };
}

// ═══════════════════════════════════════════════════════════════
// buildReport — assembles the PreflightReport object
// ═══════════════════════════════════════════════════════════════
export function buildReport(analysers: AnalyserResult[]): PreflightReport {
  const passed  = analysers.filter((a) => a.status === "PASS").length;
  const failed  = analysers.filter((a) => a.status === "FAIL").length;
  const warned  = analysers.filter((a) => a.status === "WARN").length;
  const skipped = analysers.filter((a) => a.status === "SKIP").length;

  const overallPass = failed === 0;
  const gateStatus: GateStatus =
    failed > 0 ? "FAIL" : warned > 0 ? "WARN" : "PASS";

  return {
    framework:   ENV.FRAMEWORK_NAME,
    version:     ENV.FRAMEWORK_VERSION,
    generatedAt: new Date().toISOString(),
    baseUrl:     ENV.BASE_URL,
    targetUrl:   ENV.TARGET_PAGE_URL,
    healthCheck: ENV.HEALTH_CHECK,
    gateStatus,
    overallPass,
    analysers,
    summary: {
      total:   analysers.length,
      passed,
      failed,
      warned,
      skipped,
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// saveJsonReport
// ═══════════════════════════════════════════════════════════════
export async function saveJsonReport(report: PreflightReport): Promise<string> {
  const outputDir  = path.resolve(__dirname, "../", ENV.REPORT_OUTPUT_DIR);
  await fs.ensureDir(outputDir);

  const filePath = path.join(outputDir, "preflightReport.json");
  await fs.writeJson(filePath, report, { spaces: 2 });

  logger.info(`📄 JSON report saved → ${filePath}`);
  return filePath;
}

// ═══════════════════════════════════════════════════════════════
// saveHtmlReport
// ═══════════════════════════════════════════════════════════════
export async function saveHtmlReport(report: PreflightReport): Promise<string> {
  const outputDir = path.resolve(__dirname, "../", ENV.REPORT_OUTPUT_DIR);
  await fs.ensureDir(outputDir);

  const filePath = path.join(outputDir, "preflightReport.html");
  const html     = generateHtml(report);
  await fs.writeFile(filePath, html, "utf-8");

  logger.info(`🌐 HTML report saved → ${filePath}`);
  return filePath;
}

// ═══════════════════════════════════════════════════════════════
// generateReports — saves JSON and/or HTML based on REPORT_FORMAT
// ═══════════════════════════════════════════════════════════════
export async function generateReports(
  analysers: AnalyserResult[]
): Promise<PreflightReport> {
  const report = buildReport(analysers);
  const format = ENV.REPORT_FORMAT;

  if (format === "json" || format === "both") await saveJsonReport(report);
  if (format === "html" || format === "both") await saveHtmlReport(report);

  return report;
}

// ═══════════════════════════════════════════════════════════════
// generateHtml — builds the HTML report string
// ═══════════════════════════════════════════════════════════════
function generateHtml(report: PreflightReport): string {
  const statusColor: Record<string, string> = {
    PASS: "#22c55e",
    FAIL: "#ef4444",
    WARN: "#f59e0b",
    SKIP: "#94a3b8",
  };

  const statusIcon: Record<string, string> = {
    PASS: "✅",
    FAIL: "❌",
    WARN: "⚠️",
    SKIP: "⏭️",
  };

  const analyserRows = report.analysers
    .map(
      (a) => `
      <tr>
        <td>${statusIcon[a.status]} <strong>${a.name}</strong></td>
        <td>
          <span style="
            background:${statusColor[a.status]};
            color:#fff;
            padding:2px 10px;
            border-radius:12px;
            font-size:12px;
            font-weight:600;
          ">${a.status}</span>
        </td>
        <td>${a.duration}ms</td>
        <td>${a.details}</td>
        <td><pre style="margin:0;font-size:11px;max-width:300px;overflow:auto">${
          JSON.stringify(a.findings, null, 2)
        }</pre></td>
      </tr>`
    )
    .join("");

  const gateColor = statusColor[report.gateStatus];

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ASTRA — Preflight Report</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      padding: 32px;
      min-height: 100vh;
    }
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 32px;
      padding-bottom: 20px;
      border-bottom: 1px solid #1e293b;
    }
    .logo {
      font-size: 28px;
      font-weight: 800;
      letter-spacing: 4px;
      background: linear-gradient(135deg, #6366f1, #a855f7);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .meta { font-size: 13px; color: #64748b; text-align: right; }
    .gate-badge {
      display: inline-block;
      padding: 8px 24px;
      border-radius: 999px;
      font-size: 18px;
      font-weight: 700;
      background: ${gateColor};
      color: #fff;
      margin-bottom: 24px;
      letter-spacing: 2px;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 16px;
      margin-bottom: 32px;
    }
    .summary-card {
      background: #1e293b;
      border-radius: 12px;
      padding: 20px;
      text-align: center;
    }
    .summary-card .count {
      font-size: 36px;
      font-weight: 800;
    }
    .summary-card .label {
      font-size: 12px;
      color: #64748b;
      margin-top: 4px;
      letter-spacing: 1px;
      text-transform: uppercase;
    }
    .section-title {
      font-size: 16px;
      font-weight: 700;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 2px;
      margin-bottom: 16px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: #1e293b;
      border-radius: 12px;
      overflow: hidden;
    }
    th {
      background: #0f172a;
      padding: 12px 16px;
      text-align: left;
      font-size: 12px;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 1px;
    }
    td {
      padding: 14px 16px;
      border-top: 1px solid #0f172a;
      font-size: 13px;
      vertical-align: top;
    }
    tr:hover td { background: #263348; }
    .config-box {
      background: #1e293b;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 32px;
      font-size: 13px;
    }
    .config-row {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid #0f172a;
    }
    .config-row:last-child { border-bottom: none; }
    .config-key   { color: #64748b; }
    .config-value { color: #a5b4fc; font-family: monospace; }
    footer {
      margin-top: 32px;
      text-align: center;
      font-size: 12px;
      color: #334155;
    }
  </style>
</head>
<body>

  <!-- Header -->
  <div class="header">
    <div>
      <div class="logo">✦ ASTRA</div>
      <div style="font-size:13px;color:#475569;margin-top:4px;">
        Autonomous A* Search Based Test & Reporting Architecture
      </div>
    </div>
    <div class="meta">
      <div>Generated: ${new Date(report.generatedAt).toLocaleString()}</div>
      <div>Version: ${report.version}</div>
      <div>Health Check Mode: <strong>${report.healthCheck ? "HARD STOP" : "WARN & PROCEED"}</strong></div>
    </div>
  </div>

  <!-- Gate Status -->
  <div class="gate-badge">
    ${statusIcon[report.gateStatus]} GATE STATUS: ${report.gateStatus}
  </div>

  <!-- Config -->
  <div class="section-title">Configuration</div>
  <div class="config-box">
    <div class="config-row">
      <span class="config-key">Base URL</span>
      <span class="config-value">${report.baseUrl}</span>
    </div>
    <div class="config-row">
      <span class="config-key">Target URL</span>
      <span class="config-value">${report.targetUrl}</span>
    </div>
    <div class="config-row">
      <span class="config-key">Health Check</span>
      <span class="config-value">${report.healthCheck ? "TRUE (Hard Stop)" : "FALSE (Warn & Proceed)"}</span>
    </div>
    <div class="config-row">
      <span class="config-key">Report Generated</span>
      <span class="config-value">${report.generatedAt}</span>
    </div>
  </div>

  <!-- Summary Cards -->
  <div class="section-title">Summary</div>
  <div class="summary-grid">
    <div class="summary-card">
      <div class="count" style="color:#94a3b8">${report.summary.total}</div>
      <div class="label">Total</div>
    </div>
    <div class="summary-card">
      <div class="count" style="color:#22c55e">${report.summary.passed}</div>
      <div class="label">Passed</div>
    </div>
    <div class="summary-card">
      <div class="count" style="color:#ef4444">${report.summary.failed}</div>
      <div class="label">Failed</div>
    </div>
    <div class="summary-card">
      <div class="count" style="color:#f59e0b">${report.summary.warned}</div>
      <div class="label">Warned</div>
    </div>
    <div class="summary-card">
      <div class="count" style="color:#94a3b8">${report.summary.skipped}</div>
      <div class="label">Skipped</div>
    </div>
  </div>

  <!-- Analyser Results Table -->
  <div class="section-title">Analyser Results</div>
  <table>
    <thead>
      <tr>
        <th>Analyser</th>
        <th>Status</th>
        <th>Duration</th>
        <th>Details</th>
        <th>Findings</th>
      </tr>
    </thead>
    <tbody>
      ${analyserRows}
    </tbody>
  </table>

  <footer>
    ASTRA Framework v${report.version} — ${report.framework} | Auto-generated Preflight Report
  </footer>

</body>
</html>`;
}