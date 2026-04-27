// ═══════════════════════════════════════════════════════════════
// preflight/networkInterceptorAnalyser.ts
// ASTRA Framework — Network Interceptor Analyser
// Captures all XHR/Fetch calls on target page →
// Extracts API endpoints, methods, headers, payload structure
// Builds API blueprint for codegen layer
//Key highlights:
//
// Dual interception — both page.on("request") and page.on("response") captured and merged — gives full request + response picture per endpoint
// triggerFormInteractions() — clicks first input, opens dropdowns, scrolls to bottom — forces lazy-loaded API calls to fire before capture ends
// inferSchema() — recursive type inference from live JSON payloads — builds request/response schema automatically (string/number/boolean/array/object)
// buildApiBlueprint() — deduplicates by method:path, skips auth endpoints, outputs structured blueprint ready for apiCodeGenerator
// sanitizeHeaders() — redacts authorization, cookie, x-api-key in reports — security conscious
// saveBlueprintToFile() — writes apiBlueprint.json to payloads/requests/ — apiCodeGenerator reads this directly
// IGNORE_PATTERNS — filters out JS/CSS/images/analytics noise — only captures meaningful API calls
// extractRequiredFields() — identifies non-null fields from live request body — feeds A* heuristic scorer
// ═══════════════════════════════════════════════════════════════

import { chromium, Browser, Page, Request, Response } from "@playwright/test";
import * as fs from "fs-extra";
import * as path from "path";
import { ENV } from "../utils/envLoader";
import { logger } from "../utils/logger";
import { AnalyserResult } from "../utils/reportGenerator";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export interface CapturedEndpoint {
  method:          string;
  url:             string;
  path:            string;
  statusCode:      number | null;
  requestHeaders:  Record<string, string>;
  requestBody:     Record<string, unknown> | null;
  responseBody:    Record<string, unknown> | null;
  contentType:     string;
  isAuth:          boolean;
  timestamp:       string;
}

export interface NetworkFindings {
  totalCaptured:    number;
  postEndpoints:    number;
  putEndpoints:     number;
  getEndpoints:     number;
  deleteEndpoints:  number;
  authEndpoints:    number;
  endpoints:        CapturedEndpoint[];
  apiBlueprint:     ApiBlueprint[];
  savedBlueprintTo: string;
}

export interface ApiBlueprint {
  method:         string;
  url:            string;
  path:           string;
  requestSchema:  Record<string, unknown>;
  responseSchema: Record<string, unknown>;
  requiredFields: string[];
  headers:        Record<string, string>;
}

// ═══════════════════════════════════════════════════════════════
// URL patterns to ignore — static assets
// ═══════════════════════════════════════════════════════════════
const IGNORE_PATTERNS = [
  /\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|map)(\?.*)?$/i,
  /google-analytics/i,
  /hotjar/i,
  /intercom/i,
  /segment\.io/i,
  /mixpanel/i,
  /sentry/i,
];

// ═══════════════════════════════════════════════════════════════
// runNetworkInterceptorAnalyser
// ═══════════════════════════════════════════════════════════════
export async function runNetworkInterceptorAnalyser(): Promise<AnalyserResult> {
  const start = Date.now();
  const name  = "Network Interceptor Analyser";

  logger.divider("Network Interceptor Analyser — Starting");

  if (!ENV.NETWORK_INTERCEPTOR_ENABLED) {
    logger.preflightResult(name, "SKIP", "Disabled via NETWORK_INTERCEPTOR_ENABLED=false");
    return buildResult(name, "SKIP", Date.now() - start, "Disabled in config", {});
  }

  let browser: Browser | null = null;

  try {
    browser = await chromium.launch({
      headless: ENV.HEADLESS,
      slowMo:   ENV.SLOW_MO,
    });

    const page = await browser.newPage();

    // ─── Inject Bearer token if already available ────────────
    if (ENV.BEARER_TOKEN) {
      await page.setExtraHTTPHeaders({
        Authorization: `${ENV.TOKEN_TYPE} ${ENV.BEARER_TOKEN}`,
      });
      logger.preflight("Bearer token injected into page headers");
    }

    // ─── Captured data store ─────────────────────────────────
    const capturedEndpoints: CapturedEndpoint[] = [];
    const responseBodyMap = new Map<string, Record<string, unknown>>();

    // ─── Intercept responses first to capture body ───────────
    page.on("response", async (response: Response) => {
      const url         = response.url();
      const contentType = response.headers()["content-type"] ?? "";

      if (shouldIgnore(url)) return;
      if (!contentType.includes("application/json")) return;

      try {
        const body = await response.json().catch(() => null);
        if (body) {
          responseBodyMap.set(url, body as Record<string, unknown>);
        }
      } catch {
        // Silent
      }
    });

    // ─── Intercept requests ───────────────────────────────────
    page.on("request", async (request: Request) => {
      const url    = request.url();
      const method = request.method().toUpperCase();

      if (shouldIgnore(url)) return;

      // Only capture API-like requests
      const resourceType = request.resourceType();
      if (!["xhr", "fetch", "document"].includes(resourceType)) return;

      let requestBody: Record<string, unknown> | null = null;
      const postData = request.postData();

      if (postData) {
        try {
          requestBody = JSON.parse(postData);
        } catch {
          requestBody = { rawBody: postData };
        }
      }

      const isAuth = /login|auth|token|signin|session/i.test(url);

      capturedEndpoints.push({
        method,
        url,
        path:            extractPath(url),
        statusCode:      null,         // Will be updated from response
        requestHeaders:  sanitizeHeaders(request.headers()),
        requestBody,
        responseBody:    null,         // Will be updated after response
        contentType:     request.headers()["content-type"] ?? "",
        isAuth,
        timestamp:       new Date().toISOString(),
      });
    });

    // ─── Login and navigate to target ────────────────────────
    await loginAndNavigate(page);

    // ─── Trigger form interactions to capture POST calls ─────
    await triggerFormInteractions(page);

    // ─── Wait for all network activity to settle ─────────────
    await page.waitForLoadState("networkidle").catch(() => {});
    await page.waitForTimeout(2000);

    // ─── Merge response bodies into captured endpoints ────────
    for (const endpoint of capturedEndpoints) {
      const responseBody = responseBodyMap.get(endpoint.url);
      if (responseBody) endpoint.responseBody = responseBody;
    }

    // ─── Update status codes via page responses ───────────────
    const responses = await page.evaluate(() =>
      performance
        .getEntriesByType("resource")
        .filter((e): e is PerformanceResourceTiming =>
          "responseStatus" in e
        )
        .map((e) => ({
          url:        e.name,
          statusCode: (e as any).responseStatus ?? null,
        }))
    );

    for (const r of responses) {
      const endpoint = capturedEndpoints.find((e) => e.url === r.url);
      if (endpoint) endpoint.statusCode = r.statusCode;
    }

    // ─── Build API Blueprint ──────────────────────────────────
    const apiBlueprint = buildApiBlueprint(capturedEndpoints);

    // ─── Save blueprint to payloads directory ─────────────────
    const blueprintPath = await saveBlueprintToFile(apiBlueprint);

    // ─── Build findings ───────────────────────────────────────
    const findings: NetworkFindings = {
      totalCaptured:   capturedEndpoints.length,
      postEndpoints:   capturedEndpoints.filter((e) => e.method === "POST").length,
      putEndpoints:    capturedEndpoints.filter((e) => e.method === "PUT").length,
      getEndpoints:    capturedEndpoints.filter((e) => e.method === "GET").length,
      deleteEndpoints: capturedEndpoints.filter((e) => e.method === "DELETE").length,
      authEndpoints:   capturedEndpoints.filter((e) => e.isAuth).length,
      endpoints:       capturedEndpoints,
      apiBlueprint,
      savedBlueprintTo: blueprintPath,
    };

    logger.preflight(`Total endpoints captured: ${findings.totalCaptured}`);
    logger.preflight(`POST: ${findings.postEndpoints} | PUT: ${findings.putEndpoints} | GET: ${findings.getEndpoints}`);
    logger.preflight(`API blueprint saved → ${blueprintPath}`);

    if (findings.totalCaptured === 0) {
      logger.preflightResult(name, "WARN", "No network calls captured — page may be static");
      return buildResult(
        name, "WARN", Date.now() - start,
        "No network calls captured",
        findings as unknown as Record<string, unknown>
      );
    }

    logger.preflightResult(name, "PASS", `${findings.totalCaptured} endpoints captured`);
    return buildResult(
      name, "PASS", Date.now() - start,
      `${findings.totalCaptured} endpoints captured — blueprint saved`,
      findings as unknown as Record<string, unknown>
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
// loginAndNavigate
// ═══════════════════════════════════════════════════════════════
async function loginAndNavigate(page: Page): Promise<void> {
  logger.preflight(`Navigating to login: ${ENV.LOGIN_URL}`);
  await page.goto(ENV.LOGIN_URL, { waitUntil: "networkidle" });

  const usernameSelectors = [
    'input[name="username"]', 'input[name="email"]',
    'input[type="email"]',   'input[id*="user"]',
    'input[id*="email"]',
  ];
  const passwordSelectors = [
    'input[name="password"]', 'input[type="password"]',
  ];
  const submitSelectors = [
    'button[type="submit"]', 'button:has-text("Login")',
    'button:has-text("Sign in")',
  ];

  for (const sel of usernameSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) { await el.fill(ENV.APP_USERNAME); break; }
  }
  for (const sel of passwordSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) { await el.fill(ENV.APP_PASSWORD); break; }
  }
  for (const sel of submitSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) { await el.click(); break; }
  }

  await page.waitForLoadState("networkidle").catch(() => {});
  logger.preflight(`Navigating to target: ${ENV.TARGET_PAGE_URL}`);
  await page.goto(ENV.TARGET_PAGE_URL, { waitUntil: "networkidle" });
}

// ═══════════════════════════════════════════════════════════════
// triggerFormInteractions — light interactions to reveal
// conditional fields and trigger prefetch API calls
// ═══════════════════════════════════════════════════════════════
async function triggerFormInteractions(page: Page): Promise<void> {
  logger.preflight("Triggering light form interactions to capture dynamic calls");

  try {
    // Click first input to trigger any onFocus API calls
    const firstInput = page.locator("input:visible").first();
    if (await firstInput.isVisible().catch(() => false)) {
      await firstInput.click();
      await page.waitForTimeout(500);
    }

    // Open all dropdowns to capture option-load API calls
    const dropdowns = page.locator("select:visible");
    const count     = await dropdowns.count();
    for (let i = 0; i < Math.min(count, 5); i++) {
      await dropdowns.nth(i).click().catch(() => {});
      await page.waitForTimeout(300);
    }

    // Scroll to bottom to trigger lazy-loaded sections
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);

  } catch {
    // Non-critical — continue
  }
}

// ═══════════════════════════════════════════════════════════════
// buildApiBlueprint — transforms captured endpoints into
// structured API blueprints for apiCodeGenerator
// ═══════════════════════════════════════════════════════════════
function buildApiBlueprint(endpoints: CapturedEndpoint[]): ApiBlueprint[] {
  // Deduplicate by method + path
  const seen  = new Set<string>();
  const plans: ApiBlueprint[] = [];

  for (const ep of endpoints) {
    const key = `${ep.method}:${ep.path}`;
    if (seen.has(key)) continue;
    seen.add(key);

    if (ep.isAuth) continue; // Skip auth endpoints — not test targets

    plans.push({
      method:         ep.method,
      url:            ep.url,
      path:           ep.path,
      requestSchema:  inferSchema(ep.requestBody),
      responseSchema: inferSchema(ep.responseBody),
      requiredFields: extractRequiredFields(ep.requestBody),
      headers:        {
        "Content-Type":  "application/json",
        "Authorization": `${ENV.TOKEN_TYPE} {{BEARER_TOKEN}}`,
      },
    });
  }

  return plans;
}

// ═══════════════════════════════════════════════════════════════
// inferSchema — builds a type schema from a JSON body sample
// ═══════════════════════════════════════════════════════════════
function inferSchema(
  body: Record<string, unknown> | null,
  depth = 0
): Record<string, unknown> {
  if (!body || depth > 4) return {};

  const schema: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(body)) {
    if (value === null)                         schema[key] = "null";
    else if (typeof value === "string")         schema[key] = "string";
    else if (typeof value === "number")         schema[key] = "number";
    else if (typeof value === "boolean")        schema[key] = "boolean";
    else if (Array.isArray(value))              schema[key] = "array";
    else if (typeof value === "object")         schema[key] = inferSchema(
      value as Record<string, unknown>, depth + 1
    );
    else                                        schema[key] = typeof value;
  }

  return schema;
}

// ═══════════════════════════════════════════════════════════════
// extractRequiredFields — identifies non-null fields in body
// ═══════════════════════════════════════════════════════════════
function extractRequiredFields(body: Record<string, unknown> | null): string[] {
  if (!body) return [];
  return Object.entries(body)
    .filter(([, v]) => v !== null && v !== "" && v !== undefined)
    .map(([k]) => k);
}

// ═══════════════════════════════════════════════════════════════
// saveBlueprintToFile — saves API blueprint as JSON
// ═══════════════════════════════════════════════════════════════
async function saveBlueprintToFile(blueprint: ApiBlueprint[]): Promise<string> {
  const outputDir  = path.resolve(__dirname, "../payloads/requests");
  await fs.ensureDir(outputDir);

  const filePath = path.join(outputDir, "apiBlueprint.json");
  await fs.writeJson(filePath, blueprint, { spaces: 2 });

  return filePath;
}

// ═══════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════
function shouldIgnore(url: string): boolean {
  return IGNORE_PATTERNS.some((pattern) => pattern.test(url));
}

function extractPath(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

function sanitizeHeaders(
  headers: Record<string, string>
): Record<string, string> {
  const sensitive = ["authorization", "cookie", "x-api-key", "x-auth-token"];
  const sanitized: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    sanitized[key] = sensitive.includes(key.toLowerCase())
      ? "***REDACTED***"
      : value;
  }
  return sanitized;
}

function buildResult(
  name:     string,
  status:   AnalyserResult["status"],
  duration: number,
  details:  string,
  findings: Record<string, unknown>
): AnalyserResult {
  return { name, status, duration, details, findings, timestamp: new Date().toISOString() };
}