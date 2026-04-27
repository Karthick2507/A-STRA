// ═══════════════════════════════════════════════════════════════
// utils/envLoader.ts
// ASTRA Framework — Environment Loader & Validator
// Loads .env and validates all required keys before framework runs
//Key highlights:
//
// validateEnv() — runs at startup, catches missing required keys before framework attempts anything
// OPTIONAL_DEFAULTS — framework self-heals missing optional config with sensible defaults
// ENV typed object — every file in ASTRA imports ENV instead of raw process.env — type-safe, zero typos
// HEALTH_CHECK parsed as boolean — ENV.HEALTH_CHECK === true clean comparison everywhere
// updateEnvFile() — critical utility used by bearerTokenAnalyser to write token back to .env and update process.env simultaneously in the same run
// ═══════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════
// utils/envLoader.ts
// ASTRA Framework — Environment Loader & Validator
// Loads .env and validates all required keys before framework runs
// ═══════════════════════════════════════════════════════════════

import * as dotenv from "dotenv";
import * as path from "path";
import * as fs from "fs";

// ─── Load .env file ─────────────────────────────────────────────
// Use process.cwd() — always the project root regardless of where
// this file sits. __dirname can drift depending on ts-node setup.
const envPath = (() => {
  const cwdPath    = path.resolve(process.cwd(), ".env");
  const dirnameP   = path.resolve(__dirname, "../.env");
  const dirnameP2  = path.resolve(__dirname, "../../.env");

  if (fs.existsSync(cwdPath))   return cwdPath;
  if (fs.existsSync(dirnameP))  return dirnameP;
  if (fs.existsSync(dirnameP2)) return dirnameP2;
  return cwdPath; // fallback — will fail with clear error below
})();

console.log(`[ASTRA] Loading .env from: ${envPath}`);

if (!fs.existsSync(envPath)) {
  console.error(`❌ ASTRA: .env file not found.`);
  console.error(`   Looked in:`);
  console.error(`     ${path.resolve(process.cwd(), ".env")}`);
  console.error(`     ${path.resolve(__dirname, "../.env")}`);
  console.error(`   Please create a .env file in your project root.`);
  process.exit(1);
}

dotenv.config({ path: envPath });

// ═══════════════════════════════════════════════════════════════
// Required Keys — framework cannot run without these
// ═══════════════════════════════════════════════════════════════
const REQUIRED_KEYS: string[] = [
  "BASE_URL",
  "LOGIN_URL",
  "TARGET_PAGE_URL",
  "APP_USERNAME",
  "APP_PASSWORD",
  "HEALTH_CHECK",
  "BROWSER",
  "HEADLESS",
];

// ═══════════════════════════════════════════════════════════════
// Optional Keys — with their default fallback values
// ═══════════════════════════════════════════════════════════════
const OPTIONAL_DEFAULTS: Record<string, string> = {
  SLOW_MO:                      "0",
  VIEWPORT_WIDTH:               "1280",
  VIEWPORT_HEIGHT:              "720",
  ASTAR_MAX_ITERATIONS:         "1000",
  ASTAR_HEURISTIC_WEIGHT:       "1.0",
  ASTAR_GOAL_TIMEOUT:           "30000",
  API_TIMEOUT:                  "15000",
  API_RETRY_COUNT:              "3",
  REPORT_OUTPUT_DIR:            "reports/preflight",
  TEST_REPORT_DIR:              "reports/testResults",
  REPORT_FORMAT:                "both",
  LOG_LEVEL:                    "info",
  LOG_TO_FILE:                  "true",
  LOG_FILE_PATH:                "reports/astra.log",
  DOM_ANALYSER_ENABLED:         "true",
  BEARER_TOKEN_ANALYSER_ENABLED:"true",
  NETWORK_INTERCEPTOR_ENABLED:  "true",
  ANTI_BOT_ANALYSER_ENABLED:    "true",
  TOKEN_TYPE:                   "Bearer",
  FRAMEWORK_NAME:               "ASTRA",
  FRAMEWORK_VERSION:            "1.0.0",
};

// ═══════════════════════════════════════════════════════════════
// Validation Result Interface
// ═══════════════════════════════════════════════════════════════
export interface EnvValidationResult {
  valid: boolean;
  missingKeys: string[];
  loadedKeys: string[];
  warnings: string[];
}

// ═══════════════════════════════════════════════════════════════
// validateEnv — checks all required keys are present
// ═══════════════════════════════════════════════════════════════
export function validateEnv(): EnvValidationResult {
  const missingKeys: string[] = [];
  const loadedKeys: string[]  = [];
  const warnings: string[]    = [];

  // ─── Check required keys ──────────────────────────────────────
  for (const key of REQUIRED_KEYS) {
    if (!process.env[key] || process.env[key]?.trim() === "") {
      missingKeys.push(key);
    } else {
      loadedKeys.push(key);
    }
  }

  // ─── Apply defaults for optional keys ─────────────────────────
  for (const [key, defaultValue] of Object.entries(OPTIONAL_DEFAULTS)) {
    if (!process.env[key] || process.env[key]?.trim() === "") {
      process.env[key] = defaultValue;
      warnings.push(`⚠️  ${key} not set — using default: "${defaultValue}"`);
    } else {
      loadedKeys.push(key);
    }
  }

  // ─── Warn if BEARER_TOKEN is empty (will be auto-populated) ───
  if (!process.env.BEARER_TOKEN || process.env.BEARER_TOKEN.trim() === "") {
    warnings.push(
      "⚠️  BEARER_TOKEN is empty — will be auto-populated by bearerTokenAnalyser"
    );
  }

  return {
    valid: missingKeys.length === 0,
    missingKeys,
    loadedKeys,
    warnings,
  };
}

// ═══════════════════════════════════════════════════════════════
// Typed ENV accessor — central place to read all env values
// ═══════════════════════════════════════════════════════════════
export const ENV = {
  // ─── App ──────────────────────────────────────────────────────
  BASE_URL:               process.env.BASE_URL              || "",
  LOGIN_URL:              process.env.LOGIN_URL             || "",
  TARGET_PAGE_URL:        process.env.TARGET_PAGE_URL       || "",
  APP_USERNAME:           process.env.APP_USERNAME          || "",
  APP_PASSWORD:           process.env.APP_PASSWORD          || "",

  // ─── Auth ─────────────────────────────────────────────────────
  BEARER_TOKEN:           process.env.BEARER_TOKEN          || "",
  TOKEN_TYPE:             process.env.TOKEN_TYPE            || "Bearer",
  TOKEN_EXPIRY:           process.env.TOKEN_EXPIRY          || "",

  // ─── Health Check ─────────────────────────────────────────────
  HEALTH_CHECK:           process.env.HEALTH_CHECK          === "TRUE",
  DOM_ANALYSER_ENABLED:   process.env.DOM_ANALYSER_ENABLED  !== "false",
  BEARER_TOKEN_ANALYSER_ENABLED:
                          process.env.BEARER_TOKEN_ANALYSER_ENABLED !== "false",
  NETWORK_INTERCEPTOR_ENABLED:
                          process.env.NETWORK_INTERCEPTOR_ENABLED   !== "false",
  ANTI_BOT_ANALYSER_ENABLED:
                          process.env.ANTI_BOT_ANALYSER_ENABLED     !== "false",

  // ─── Browser ──────────────────────────────────────────────────
  BROWSER:                process.env.BROWSER               || "chromium",
  HEADLESS:               process.env.HEADLESS              !== "false",
  SLOW_MO:                parseInt(process.env.SLOW_MO      || "0", 10),
  VIEWPORT_WIDTH:         parseInt(process.env.VIEWPORT_WIDTH  || "1280", 10),
  VIEWPORT_HEIGHT:        parseInt(process.env.VIEWPORT_HEIGHT || "720",  10),

  // ─── A* Engine ────────────────────────────────────────────────
  ASTAR_MAX_ITERATIONS:   parseInt(process.env.ASTAR_MAX_ITERATIONS    || "1000", 10),
  ASTAR_HEURISTIC_WEIGHT: parseFloat(process.env.ASTAR_HEURISTIC_WEIGHT || "1.0"),
  ASTAR_GOAL_TIMEOUT:     parseInt(process.env.ASTAR_GOAL_TIMEOUT       || "30000", 10),

  // ─── API ──────────────────────────────────────────────────────
  API_BASE_URL:           process.env.API_BASE_URL          || "",
  API_TIMEOUT:            parseInt(process.env.API_TIMEOUT  || "15000", 10),
  API_RETRY_COUNT:        parseInt(process.env.API_RETRY_COUNT || "3", 10),

  // ─── Reports ──────────────────────────────────────────────────
  REPORT_OUTPUT_DIR:      process.env.REPORT_OUTPUT_DIR     || "reports/preflight",
  TEST_REPORT_DIR:        process.env.TEST_REPORT_DIR       || "reports/testResults",
  REPORT_FORMAT:          process.env.REPORT_FORMAT         || "both",

  // ─── Logger ───────────────────────────────────────────────────
  LOG_LEVEL:              process.env.LOG_LEVEL             || "info",
  LOG_TO_FILE:            process.env.LOG_TO_FILE           !== "false",
  LOG_FILE_PATH:          process.env.LOG_FILE_PATH         || "reports/astra.log",

  // ─── Meta ─────────────────────────────────────────────────────
  FRAMEWORK_NAME:         process.env.FRAMEWORK_NAME        || "ASTRA",
  FRAMEWORK_VERSION:      process.env.FRAMEWORK_VERSION     || "1.0.0",
};

// ═══════════════════════════════════════════════════════════════
// updateEnvFile — writes a key=value back to .env file
// Used by bearerTokenAnalyser to persist BEARER_TOKEN
// ═══════════════════════════════════════════════════════════════
export function updateEnvFile(key: string, value: string): void {
  const envContent = fs.readFileSync(envPath, "utf-8");
  const keyRegex   = new RegExp(`^${key}=.*$`, "m");

  const updated = keyRegex.test(envContent)
    ? envContent.replace(keyRegex, `${key}=${value}`)
    : `${envContent}\n${key}=${value}`;

  fs.writeFileSync(envPath, updated, "utf-8");

  // Also update in-memory process.env
  process.env[key] = value;
}