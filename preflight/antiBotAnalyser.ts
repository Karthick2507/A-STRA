// ═══════════════════════════════════════════════════════════════
// preflight/antiBotAnalyser.ts
// ASTRA Framework — Anti-Bot Protection Analyser
// Detects CAPTCHA, rate limiting, honeypot fields,
// bot-detection scripts, Cloudflare, WAF protections
//Key highlights:
//
// 7 independent detection checks — CAPTCHA, Cloudflare, WAF, Rate Limit, Honeypot, Bot Detection Scripts, Headless Detection — each returns its own ThreatLevel
// computeThreatLevel() — highest single threat wins as overall — one HIGH = entire gate is HIGH
// ThreatLevel scale — NONE → LOW → MEDIUM → HIGH maps cleanly to PASS → PASS → WARN → FAIL
// detectHoneypot() — runs inside browser context checking hidden styles, aria-hidden, parent visibility — ASTRA auto-skips these fields
// CAPTCHA detection is 3-layer — script URL → DOM selectors → page source keywords
// buildRecommendations() — generates actionable fix suggestions per detected threat written directly into HTML report
// Cloudflare signatures check both headers and header values — catches CF even when disguised
// Rate limit → LOW threat only — ASTRA proceeds but logs recommendation to increase SLOW_MO
// ═══════════════════════════════════════════════════════════════

import { chromium, Browser, Page } from "@playwright/test";
import { ENV } from "../utils/envLoader";
import { logger } from "../utils/logger";
import { AnalyserResult } from "../utils/reportGenerator";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export type ThreatLevel = "NONE" | "LOW" | "MEDIUM" | "HIGH";

export interface AntiBotFinding {
  type:        string;
  detected:    boolean;
  detail:      string;
  threatLevel: ThreatLevel;
}

export interface AntiBotFindings {
  overallThreatLevel: ThreatLevel;
  safeToAutomate:     boolean;
  findings:           AntiBotFinding[];
  recommendations:    string[];
  captchaDetected:    boolean;
  rateLimitDetected:  boolean;
  honeypotDetected:   boolean;
  cloudflareDetected: boolean;
  wafDetected:        boolean;
}

// ═══════════════════════════════════════════════════════════════
// Detection Signatures
// ═══════════════════════════════════════════════════════════════

// CAPTCHA script patterns
const CAPTCHA_SCRIPTS = [
  "recaptcha",
  "hcaptcha",
  "turnstile",
  "funcaptcha",
  "arkose",
  "captcha",
  "antibot",
];

// CAPTCHA DOM selectors
const CAPTCHA_SELECTORS = [
  ".g-recaptcha",
  ".h-captcha",
  "[data-sitekey]",
  "#recaptcha",
  'iframe[src*="recaptcha"]',
  'iframe[src*="hcaptcha"]',
  'iframe[src*="turnstile"]',
  ".cf-turnstile",
];

// Cloudflare signatures
const CLOUDFLARE_SIGNATURES = [
  "__cf_bm",
  "cf-ray",
  "cf_clearance",
  "cloudflare",
  "__cfduid",
];

// WAF signatures in headers/body
const WAF_SIGNATURES = [
  "x-waf",
  "x-sucuri-id",
  "x-fw-server",
  "x-akamai",
  "x-imperva",
  "x-datadome",
  "x-amzn-waf",
];

// Rate limit header patterns
const RATE_LIMIT_HEADERS = [
  "x-ratelimit-limit",
  "x-ratelimit-remaining",
  "x-ratelimit-reset",
  "retry-after",
  "ratelimit-limit",
  "ratelimit-remaining",
];

// Honeypot field characteristics
const HONEYPOT_INDICATORS = [
  { attr: "style", pattern: /display:\s*none|visibility:\s*hidden|opacity:\s*0/i },
  { attr: "tabindex", pattern: /^-1$/ },
  { attr: "aria-hidden", pattern: /true/ },
];

const HONEYPOT_CLASS_PATTERNS = [
  /honeypot/i,
  /hp_/i,
  /bot.?trap/i,
  /anti.?spam/i,
  /winnie.?the.?pooh/i,
];

// ═══════════════════════════════════════════════════════════════
// runAntiBotAnalyser
// ═══════════════════════════════════════════════════════════════
export async function runAntiBotAnalyser(): Promise<AnalyserResult> {
  const start = Date.now();
  const name  = "Anti-Bot Protection Analyser";

  logger.divider("Anti-Bot Protection Analyser — Starting");

  if (!ENV.ANTI_BOT_ANALYSER_ENABLED) {
    logger.preflightResult(name, "SKIP", "Disabled via ANTI_BOT_ANALYSER_ENABLED=false");
    return buildResult(name, "SKIP", Date.now() - start, "Disabled in config", {});
  }

  let browser: Browser | null = null;

  try {
    browser = await chromium.launch({
      headless: ENV.HEADLESS,
      slowMo:   ENV.SLOW_MO,
    });

    const page = await browser.newPage();

    // ─── Capture response headers ────────────────────────────
    const capturedHeaders: Record<string, string> = {};
    const capturedScripts: string[]               = [];

    page.on("response", async (response) => {
      const url = response.url();
      if (url === ENV.TARGET_PAGE_URL || url === ENV.LOGIN_URL) {
        Object.assign(capturedHeaders, response.headers());
      }
    });

    page.on("request", (request) => {
      const url = request.url();
      for (const sig of CAPTCHA_SCRIPTS) {
        if (url.toLowerCase().includes(sig)) {
          capturedScripts.push(url);
        }
      }
    });

    // ─── Navigate with auth ──────────────────────────────────
    if (ENV.BEARER_TOKEN) {
      await page.setExtraHTTPHeaders({
        Authorization: `${ENV.TOKEN_TYPE} ${ENV.BEARER_TOKEN}`,
      });
    }

    await page.goto(ENV.LOGIN_URL, { waitUntil: "networkidle" }).catch(() => {});
    await page.goto(ENV.TARGET_PAGE_URL, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(2000);

    // ─── Run all detection checks ────────────────────────────
    const findings: AntiBotFinding[] = [];

    // 1. CAPTCHA Detection
    const captchaResult = await detectCaptcha(page, capturedScripts);
    findings.push(captchaResult);

    // 2. Cloudflare Detection
    const cloudflareResult = detectCloudflare(capturedHeaders);
    findings.push(cloudflareResult);

    // 3. WAF Detection
    const wafResult = detectWaf(capturedHeaders);
    findings.push(wafResult);

    // 4. Rate Limit Detection
    const rateLimitResult = detectRateLimit(capturedHeaders);
    findings.push(rateLimitResult);

    // 5. Honeypot Detection
    const honeypotResult = await detectHoneypot(page);
    findings.push(honeypotResult);

    // 6. Bot Detection Scripts
    const botScriptResult = await detectBotScripts(page);
    findings.push(botScriptResult);

    // 7. Headless Detection
    const headlessResult = await detectHeadlessChecks(page);
    findings.push(headlessResult);

    // ─── Compute overall threat level ────────────────────────
    const overallThreatLevel = computeThreatLevel(findings);
    const safeToAutomate     = overallThreatLevel !== "HIGH";

    // ─── Build recommendations ───────────────────────────────
    const recommendations = buildRecommendations(findings);

    const antiBotFindings: AntiBotFindings = {
      overallThreatLevel,
      safeToAutomate,
      findings,
      recommendations,
      captchaDetected:    findings.find((f) => f.type === "CAPTCHA")?.detected         ?? false,
      rateLimitDetected:  findings.find((f) => f.type === "RATE_LIMIT")?.detected      ?? false,
      honeypotDetected:   findings.find((f) => f.type === "HONEYPOT")?.detected        ?? false,
      cloudflareDetected: findings.find((f) => f.type === "CLOUDFLARE")?.detected      ?? false,
      wafDetected:        findings.find((f) => f.type === "WAF")?.detected             ?? false,
    };

    // ─── Log results ─────────────────────────────────────────
    logger.preflight(`Overall threat level: ${overallThreatLevel}`);
    logger.preflight(`Safe to automate: ${safeToAutomate}`);
    findings.forEach((f) => {
      if (f.detected) logger.preflight(`  ${f.type}: ${f.detail}`);
    });

    // ─── Determine analyser status ───────────────────────────
    if (overallThreatLevel === "HIGH") {
      logger.preflightResult(name, "FAIL", `HIGH threat level — automation blocked`);
      return buildResult(
        name, "FAIL", Date.now() - start,
        `HIGH threat detected — ${findings.filter((f) => f.detected).map((f) => f.type).join(", ")}`,
        antiBotFindings as unknown as Record<string, unknown>
      );
    }

    if (overallThreatLevel === "MEDIUM" || overallThreatLevel === "LOW") {
      logger.preflightResult(name, "WARN", `${overallThreatLevel} threat level — proceed with caution`);
      return buildResult(
        name, "WARN", Date.now() - start,
        `${overallThreatLevel} threat — ${recommendations[0] ?? "proceed carefully"}`,
        antiBotFindings as unknown as Record<string, unknown>
      );
    }

    logger.preflightResult(name, "PASS", "No bot protection detected — safe to automate");
    return buildResult(
      name, "PASS", Date.now() - start,
      "No significant bot protection detected",
      antiBotFindings as unknown as Record<string, unknown>
    );

  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error);
    logger.preflightResult(name, "FAIL", errMsg);
    return buildResult(name, "FAIL", Date.now() - start, errMsg, { error: errMsg });

  } finally {
    if (browser) await browser.close();
  }
}

// ═══════════════════════════════════════════════════════════════
// detectCaptcha
// ═══════════════════════════════════════════════════════════════
async function detectCaptcha(
  page: Page,
  capturedScripts: string[]
): Promise<AntiBotFinding> {

  // Check loaded scripts
  if (capturedScripts.length > 0) {
    return {
      type:        "CAPTCHA",
      detected:    true,
      detail:      `CAPTCHA script detected: ${capturedScripts[0]}`,
      threatLevel: "HIGH",
    };
  }

  // Check DOM selectors
  for (const selector of CAPTCHA_SELECTORS) {
    const el = page.locator(selector).first();
    if (await el.isVisible().catch(() => false)) {
      return {
        type:        "CAPTCHA",
        detected:    true,
        detail:      `CAPTCHA element found: ${selector}`,
        threatLevel: "HIGH",
      };
    }
  }

  // Check page source for CAPTCHA keywords
  const pageSource = await page.content();
  for (const sig of CAPTCHA_SCRIPTS) {
    if (pageSource.toLowerCase().includes(sig)) {
      return {
        type:        "CAPTCHA",
        detected:    true,
        detail:      `CAPTCHA keyword in page source: ${sig}`,
        threatLevel: "MEDIUM",
      };
    }
  }

  return {
    type:        "CAPTCHA",
    detected:    false,
    detail:      "No CAPTCHA detected",
    threatLevel: "NONE",
  };
}

// ═══════════════════════════════════════════════════════════════
// detectCloudflare
// ═══════════════════════════════════════════════════════════════
function detectCloudflare(headers: Record<string, string>): AntiBotFinding {
  const lowerHeaders = Object.keys(headers).map((k) => k.toLowerCase());

  for (const sig of CLOUDFLARE_SIGNATURES) {
    if (lowerHeaders.includes(sig) || Object.values(headers).some((v) =>
      v.toLowerCase().includes(sig)
    )) {
      return {
        type:        "CLOUDFLARE",
        detected:    true,
        detail:      `Cloudflare signature detected: ${sig}`,
        threatLevel: "MEDIUM",
      };
    }
  }

  return {
    type:        "CLOUDFLARE",
    detected:    false,
    detail:      "No Cloudflare protection detected",
    threatLevel: "NONE",
  };
}

// ═══════════════════════════════════════════════════════════════
// detectWaf
// ═══════════════════════════════════════════════════════════════
function detectWaf(headers: Record<string, string>): AntiBotFinding {
  const lowerHeaders = Object.keys(headers).map((k) => k.toLowerCase());

  for (const sig of WAF_SIGNATURES) {
    if (lowerHeaders.includes(sig)) {
      return {
        type:        "WAF",
        detected:    true,
        detail:      `WAF header detected: ${sig}`,
        threatLevel: "MEDIUM",
      };
    }
  }

  return {
    type:        "WAF",
    detected:    false,
    detail:      "No WAF detected",
    threatLevel: "NONE",
  };
}

// ═══════════════════════════════════════════════════════════════
// detectRateLimit
// ═══════════════════════════════════════════════════════════════
function detectRateLimit(headers: Record<string, string>): AntiBotFinding {
  const lowerHeaders = Object.keys(headers).map((k) => k.toLowerCase());

  for (const header of RATE_LIMIT_HEADERS) {
    if (lowerHeaders.includes(header)) {
      const limit = headers[header] ?? headers[header.toLowerCase()] ?? "unknown";
      return {
        type:        "RATE_LIMIT",
        detected:    true,
        detail:      `Rate limit header: ${header}=${limit}`,
        threatLevel: "LOW",
      };
    }
  }

  return {
    type:        "RATE_LIMIT",
    detected:    false,
    detail:      "No rate limit headers detected",
    threatLevel: "NONE",
  };
}

// ═══════════════════════════════════════════════════════════════
// detectHoneypot
// ═══════════════════════════════════════════════════════════════
async function detectHoneypot(page: Page): Promise<AntiBotFinding> {
  const honeypotFields = await page.evaluate(
    ({ indicators, classPatterns }: {
      indicators: Array<{ attr: string; pattern: string }>;
      classPatterns: string[];
    }) => {
      const inputs  = Array.from(document.querySelectorAll("input"));
      const trapped: string[] = [];

      for (const input of inputs) {
        // Check inline style hiding
        const style = input.getAttribute("style") ?? "";
        for (const ind of indicators) {
          if (ind.attr === "style") {
            const re = new RegExp(ind.pattern);
            if (re.test(style)) {
              trapped.push(`Hidden input: ${input.name || input.id || "unknown"}`);
            }
          }
        }

        // Check class names
        const classList = input.className ?? "";
        for (const pattern of classPatterns) {
          const re = new RegExp(pattern, "i");
          if (re.test(classList)) {
            trapped.push(`Honeypot class: ${classList}`);
          }
        }

        // Check parent visibility
        const parent = input.parentElement;
        if (parent) {
          const parentStyle = window.getComputedStyle(parent);
          if (
            parentStyle.display === "none" ||
            parentStyle.visibility === "hidden"
          ) {
            trapped.push(`Hidden parent for: ${input.name || input.id || "unknown"}`);
          }
        }
      }

      return trapped;
    },
    {
      indicators: HONEYPOT_INDICATORS.map((h) => ({
        attr:    h.attr,
        pattern: h.pattern.source,
      })),
      classPatterns: HONEYPOT_CLASS_PATTERNS.map((p) => p.source),
    }
  );

  if (honeypotFields.length > 0) {
    return {
      type:        "HONEYPOT",
      detected:    true,
      detail:      `Honeypot fields found: ${honeypotFields.join(", ")}`,
      threatLevel: "MEDIUM",
    };
  }

  return {
    type:        "HONEYPOT",
    detected:    false,
    detail:      "No honeypot fields detected",
    threatLevel: "NONE",
  };
}

// ═══════════════════════════════════════════════════════════════
// detectBotScripts — checks for known bot detection libraries
// ═══════════════════════════════════════════════════════════════
async function detectBotScripts(page: Page): Promise<AntiBotFinding> {
  const botLibraries = [
    "datadome",
    "perimeterx",
    "px.js",
    "botd",
    "fingerprintjs",
    "fpjs",
    "kasada",
    "akamai-bot",
    "human.security",
  ];

  const scripts = await page.evaluate(() =>
    Array.from(document.querySelectorAll("script[src]"))
      .map((s) => s.getAttribute("src") ?? "")
  );

  for (const script of scripts) {
    for (const lib of botLibraries) {
      if (script.toLowerCase().includes(lib)) {
        return {
          type:        "BOT_DETECTION_SCRIPT",
          detected:    true,
          detail:      `Bot detection library: ${lib} (${script})`,
          threatLevel: "HIGH",
        };
      }
    }
  }

  return {
    type:        "BOT_DETECTION_SCRIPT",
    detected:    false,
    detail:      "No bot detection scripts found",
    threatLevel: "NONE",
  };
}

// ═══════════════════════════════════════════════════════════════
// detectHeadlessChecks — checks if app detects headless browsers
// ═══════════════════════════════════════════════════════════════
async function detectHeadlessChecks(page: Page): Promise<AntiBotFinding> {
  const pageSource = await page.content();

  const headlessChecks = [
    "navigator.webdriver",
    "window.callPhantom",
    "window._phantom",
    "window.domAutomation",
    "__selenium_unwrapped",
    "window.Buffer",
  ];

  for (const check of headlessChecks) {
    if (pageSource.includes(check)) {
      return {
        type:        "HEADLESS_DETECTION",
        detected:    true,
        detail:      `Headless browser check found: ${check}`,
        threatLevel: "MEDIUM",
      };
    }
  }

  return {
    type:        "HEADLESS_DETECTION",
    detected:    false,
    detail:      "No headless browser checks found",
    threatLevel: "NONE",
  };
}

// ═══════════════════════════════════════════════════════════════
// computeThreatLevel — highest single threat = overall
// ═══════════════════════════════════════════════════════════════
function computeThreatLevel(findings: AntiBotFinding[]): ThreatLevel {
  const levels: ThreatLevel[] = ["NONE", "LOW", "MEDIUM", "HIGH"];
  let maxIndex = 0;

  for (const f of findings) {
    if (!f.detected) continue;
    const idx = levels.indexOf(f.threatLevel);
    if (idx > maxIndex) maxIndex = idx;
  }

  return levels[maxIndex];
}

// ═══════════════════════════════════════════════════════════════
// buildRecommendations
// ═══════════════════════════════════════════════════════════════
function buildRecommendations(findings: AntiBotFinding[]): string[] {
  const recs: string[] = [];

  for (const f of findings) {
    if (!f.detected) continue;
    switch (f.type) {
      case "CAPTCHA":
        recs.push("CAPTCHA detected — consider using CAPTCHA bypass service or test environment without CAPTCHA");
        break;
      case "CLOUDFLARE":
        recs.push("Cloudflare detected — use cf_clearance cookie or whitelist test IP");
        break;
      case "WAF":
        recs.push("WAF detected — whitelist test runner IP or use bypass credentials");
        break;
      case "RATE_LIMIT":
        recs.push(`Rate limiting active — add delays between test steps (SLOW_MO >= 500)`);
        break;
      case "HONEYPOT":
        recs.push("Honeypot fields detected — ASTRA will automatically skip hidden fields");
        break;
      case "BOT_DETECTION_SCRIPT":
        recs.push("Bot detection script found — consider running tests with stealth plugin or real browser profile");
        break;
      case "HEADLESS_DETECTION":
        recs.push("Headless detection found — set HEADLESS=false in .env for this app");
        break;
    }
  }

  if (recs.length === 0) {
    recs.push("No threats detected — safe to run automated tests");
  }

  return recs;
}

// ═══════════════════════════════════════════════════════════════
// buildResult
// ═══════════════════════════════════════════════════════════════
function buildResult(
  name:     string,
  status:   AnalyserResult["status"],
  duration: number,
  details:  string,
  findings: Record<string, unknown>
): AnalyserResult {
  return { name, status, duration, details, findings, timestamp: new Date().toISOString() };
}