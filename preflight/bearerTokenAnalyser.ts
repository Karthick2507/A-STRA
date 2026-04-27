// ═══════════════════════════════════════════════════════════════
// preflight/bearerTokenAnalyser.ts
// ASTRA Framework — Bearer Token Analyser
// Intercepts login network call → extracts Bearer token →
// saves to .env → validates token against a known endpoint
//Key highlights:
//
// 3-layer token extraction strategy — response body → request headers → browser localStorage/sessionStorage — covers virtually all auth implementations
// extractTokenFromBody() — recursive JSON search up to 5 levels deep for nested token keys (access_token, jwt, bearer, authToken etc.)
// JWT auto-detection via regex xxx.xxx.xxx pattern — even finds tokens stored under unknown keys in localStorage
// validateToken() — tries multiple candidate endpoints (/me, /profile, /user, /whoami) automatically — no manual config needed
// tokenPreview — stores only first 20 chars in report — security conscious, never logs full token
// updateEnvFile() — persists token AND expiry back to .env live during the run
// WARN not FAIL if token found but validation endpoint returns non-2xx — framework proceeds cautiously
// ═══════════════════════════════════════════════════════════════

import { chromium, Browser, Page, Request, Response } from "@playwright/test";
import { ENV } from "../utils/envLoader";
import { updateEnvFile } from "../utils/envLoader";
import { logger } from "../utils/logger";
import { AnalyserResult } from "../utils/reportGenerator";
import axios from "axios";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export interface TokenFindings {
  tokenFound:       boolean;
  tokenType:        string;
  tokenPreview:     string;       // First 20 chars only — security
  tokenSavedToEnv:  boolean;
  validationStatus: number | null;
  validationUrl:    string;
  interceptedFrom:  string;       // URL that returned the token
  tokenExpiry:      string | null;
  tokenLength:      number;
}

// ═══════════════════════════════════════════════════════════════
// Token extraction patterns
// ═══════════════════════════════════════════════════════════════
const TOKEN_RESPONSE_KEYS = [
  "token",
  "access_token",
  "accessToken",
  "bearer",
  "jwt",
  "id_token",
  "idToken",
  "auth_token",
  "authToken",
];

const TOKEN_HEADER_PATTERNS = [
  /Bearer\s([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)/,  // JWT
  /Bearer\s([A-Za-z0-9\-_]{20,})/,                                   // Opaque token
  /^([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)$/,         // Raw JWT
];

// ═══════════════════════════════════════════════════════════════
// runBearerTokenAnalyser
// ═══════════════════════════════════════════════════════════════
export async function runBearerTokenAnalyser(): Promise<AnalyserResult> {
  const start = Date.now();
  const name  = "Bearer Token Analyser";

  logger.divider("Bearer Token Analyser — Starting");

  if (!ENV.BEARER_TOKEN_ANALYSER_ENABLED) {
    logger.preflightResult(name, "SKIP", "Disabled via BEARER_TOKEN_ANALYSER_ENABLED=false");
    return buildResult(name, "SKIP", Date.now() - start, "Disabled in config", {});
  }

  let browser: Browser | null = null;

  try {
    browser = await chromium.launch({
      headless: ENV.HEADLESS,
      slowMo:   ENV.SLOW_MO,
    });

    const page = await browser.newPage();

    // ─── Intercept all network responses ──────────────────────
    let extractedToken: string | null = null;
    let interceptedFrom: string       = "";
    let tokenExpiry: string | null    = null;

    page.on("response", async (response: Response) => {
      if (extractedToken) return; // Already found

      const url         = response.url();
      const contentType = response.headers()["content-type"] ?? "";

      // Only inspect JSON responses
      if (!contentType.includes("application/json")) return;

      // Focus on auth-related endpoints
      const isAuthUrl = /login|auth|token|signin|session/i.test(url);
      if (!isAuthUrl) return;

      try {
        const body = await response.json().catch(() => null);
        if (!body) return;

        // ─── Search response body for token keys ─────────────
        const token = extractTokenFromBody(body);
        if (token) {
          extractedToken  = token;
          interceptedFrom = url;
          tokenExpiry     = extractExpiry(body);
          logger.preflight(`Token intercepted from: ${url}`);
        }
      } catch {
        // Silent — response may not be JSON parseable
      }
    });

    // ─── Also intercept request headers on subsequent calls ───
    page.on("request", (request: Request) => {
      if (extractedToken) return;
      const authHeader = request.headers()["authorization"] ?? "";
      if (!authHeader) return;

      for (const pattern of TOKEN_HEADER_PATTERNS) {
        const match = authHeader.match(pattern);
        if (match?.[1]) {
          extractedToken  = match[1];
          interceptedFrom = request.url();
          logger.preflight(`Token found in request header: ${request.url()}`);
          break;
        }
      }
    });

    // ─── Perform login to trigger auth network call ───────────
    logger.preflight(`Navigating to login: ${ENV.LOGIN_URL}`);
    await page.goto(ENV.LOGIN_URL, { waitUntil: "networkidle" });
    await performLogin(page);

    // ─── Wait briefly for async token responses ───────────────
    await page.waitForTimeout(3000);

    // ─── Also check localStorage / sessionStorage ─────────────
    if (!extractedToken) {
      extractedToken = await extractTokenFromStorage(page);
      if (extractedToken) {
        interceptedFrom = "browser-storage";
        logger.preflight("Token found in browser localStorage/sessionStorage");
      }
    }

    // ─── Token found? ─────────────────────────────────────────
    if (!extractedToken) {
      logger.preflightResult(name, "FAIL", "No Bearer token found in network calls or storage");
      return buildResult(
        name, "FAIL", Date.now() - start,
        "Token not found — check login credentials or token key names",
        {
          tokenFound:       false,
          tokenSavedToEnv:  false,
          validationStatus: null,
          validationUrl:    "",
          interceptedFrom:  "",
          tokenExpiry:      null,
          tokenLength:      0,
          tokenPreview:     "",
          tokenType:        "",
        } as unknown as Record<string, unknown>
      );
    }

    // ─── Save token to .env ───────────────────────────────────
    updateEnvFile("BEARER_TOKEN", extractedToken);
    if (tokenExpiry) updateEnvFile("TOKEN_EXPIRY", tokenExpiry);
    logger.preflight("Bearer token saved to .env");

    // ─── Validate token ───────────────────────────────────────
    const { validationStatus, validationUrl } = await validateToken(extractedToken);

    const tokenFindings: TokenFindings = {
      tokenFound:       true,
      tokenType:        ENV.TOKEN_TYPE,
      tokenPreview:     extractedToken.substring(0, 20) + "...",
      tokenSavedToEnv:  true,
      validationStatus,
      validationUrl,
      interceptedFrom,
      tokenExpiry,
      tokenLength:      extractedToken.length,
    };

    // ─── Determine pass/fail based on validation ──────────────
    const isValid = validationStatus !== null && validationStatus < 400;

    if (isValid) {
      logger.preflightResult(name, "PASS", `Token valid — HTTP ${validationStatus}`);
      return buildResult(
        name, "PASS", Date.now() - start,
        `Token extracted & validated (HTTP ${validationStatus})`,
        tokenFindings as unknown as Record<string, unknown>
      );
    } else {
      logger.preflightResult(name, "WARN", `Token extracted but validation returned HTTP ${validationStatus}`);
      return buildResult(
        name, "WARN", Date.now() - start,
        `Token saved but validation returned HTTP ${validationStatus}`,
        tokenFindings as unknown as Record<string, unknown>
      );
    }

  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error);
    logger.preflightResult(name, "FAIL", errMsg);
    return buildResult(name, "FAIL", Date.now() - start, errMsg, { error: errMsg });

  } finally {
    if (browser) await browser.close();
  }
}

// ═══════════════════════════════════════════════════════════════
// performLogin — fills login form and submits
// ═══════════════════════════════════════════════════════════════
async function performLogin(page: Page): Promise<void> {
  const usernameSelectors = [
    'input[name="username"]',
    'input[name="email"]',
    'input[type="email"]',
    'input[id*="user"]',
    'input[id*="email"]',
    'input[placeholder*="email" i]',
    'input[placeholder*="username" i]',
  ];

  const passwordSelectors = [
    'input[name="password"]',
    'input[type="password"]',
    'input[id*="pass"]',
  ];

  const submitSelectors = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Login")',
    'button:has-text("Sign in")',
    'button:has-text("Log in")',
  ];

  for (const sel of usernameSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      await el.fill(ENV.APP_USERNAME);
      break;
    }
  }

  for (const sel of passwordSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      await el.fill(ENV.APP_PASSWORD);
      break;
    }
  }

  for (const sel of submitSelectors) {
    const el = page.locator(sel).first();
    if (await el.isVisible().catch(() => false)) {
      await el.click();
      break;
    }
  }

  await page.waitForLoadState("networkidle").catch(() => {});
}

// ═══════════════════════════════════════════════════════════════
// extractTokenFromBody — recursively searches response JSON
// ═══════════════════════════════════════════════════════════════
function extractTokenFromBody(body: Record<string, unknown>, depth = 0): string | null {
  if (depth > 5) return null; // Prevent infinite recursion

  for (const key of TOKEN_RESPONSE_KEYS) {
    if (body[key] && typeof body[key] === "string") {
      const val = body[key] as string;
      if (val.length > 10) return val; // Basic length sanity check
    }
  }

  // Recurse into nested objects
  for (const value of Object.values(body)) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const found = extractTokenFromBody(value as Record<string, unknown>, depth + 1);
      if (found) return found;
    }
  }

  return null;
}

// ═══════════════════════════════════════════════════════════════
// extractExpiry — looks for token expiry in response body
// ═══════════════════════════════════════════════════════════════
function extractExpiry(body: Record<string, unknown>): string | null {
  const expiryKeys = ["expires_in", "expiresIn", "exp", "expiry", "token_expiry"];
  for (const key of expiryKeys) {
    if (body[key]) return String(body[key]);
  }
  return null;
}

// ═══════════════════════════════════════════════════════════════
// extractTokenFromStorage — checks browser storage
// ═══════════════════════════════════════════════════════════════
async function extractTokenFromStorage(page: Page): Promise<string | null> {
  return await page.evaluate((keys: string[]) => {
    // Check localStorage
    for (const key of keys) {
      const val = localStorage.getItem(key);
      if (val && val.length > 10) return val;
    }
    // Check sessionStorage
    for (const key of keys) {
      const val = sessionStorage.getItem(key);
      if (val && val.length > 10) return val;
    }
    // Check all localStorage keys for JWT pattern
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key) continue;
      const val = localStorage.getItem(key) ?? "";
      // JWT pattern: xxx.xxx.xxx
      if (/^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+$/.test(val)) {
        return val;
      }
    }
    return null;
  }, TOKEN_RESPONSE_KEYS);
}

// ═══════════════════════════════════════════════════════════════
// validateToken — hits API endpoint to confirm token is live
// ═══════════════════════════════════════════════════════════════
async function validateToken(
  token: string
): Promise<{ validationStatus: number | null; validationUrl: string }> {

  // Use API_BASE_URL/me or /profile or /user as validation endpoint
  const candidateUrls = [
    `${ENV.API_BASE_URL}/me`,
    `${ENV.API_BASE_URL}/profile`,
    `${ENV.API_BASE_URL}/user`,
    `${ENV.API_BASE_URL}/whoami`,
    `${ENV.BASE_URL}/api/me`,
  ].filter((u) => u && !u.startsWith("/"));

  for (const url of candidateUrls) {
    try {
      logger.preflight(`Validating token against: ${url}`);
      const response = await axios.get(url, {
        headers: {
          Authorization: `${ENV.TOKEN_TYPE} ${token}`,
          "Content-Type": "application/json",
        },
        timeout:          ENV.API_TIMEOUT,
        validateStatus:   () => true,  // Don't throw on non-2xx
      });

      logger.preflight(`Validation response: HTTP ${response.status} from ${url}`);
      return { validationStatus: response.status, validationUrl: url };

    } catch {
      // Try next URL
      continue;
    }
  }

  logger.warn("Token validation — no candidate URL responded");
  return { validationStatus: null, validationUrl: "" };
}

// ═══════════════════════════════════════════════════════════════
// buildResult — helper
// ═══════════════════════════════════════════════════════════════
function buildResult(
  name:     string,
  status:   AnalyserResult["status"],
  duration: number,
  details:  string,
  findings: Record<string, unknown>
): AnalyserResult {
  return {
    name,
    status,
    duration,
    details,
    findings,
    timestamp: new Date().toISOString(),
  };
}