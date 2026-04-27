// ═══════════════════════════════════════════════════════════════
// utils/logger.ts
// ASTRA Framework — Centralized Logger
// Winston based logger with console + file transport
//Key highlights:
//
// 3 custom log levels on top of standard winston — preflight, astar, codegen — each color coded for instant visual scanning in terminal
// logger.preflightResult() — dedicated method prints ✅ ❌ ⚠️ ⏭️ status per analyser cleanly
// logger.astarStep() — logs every A* iteration with g, h, f scores — full algorithm transparency
// logger.goalReached() — 🎯 prints the exact winning path A* took to reach goal
// logger.divider() — visual section separator keeps long log runs readable
// File transport with 5MB rotation + 3 file history — logs never grow unbounded
// JSON format in file, colored format in console — best of both worlds
// ═══════════════════════════════════════════════════════════════

import * as winston from "winston";
import * as path from "path";
import * as fs from "fs-extra";
import { ENV } from "./envLoader";

// ─── Ensure log directory exists ────────────────────────────────
const logFilePath = path.resolve(__dirname, "../", ENV.LOG_FILE_PATH);
fs.ensureDirSync(path.dirname(logFilePath));

// ═══════════════════════════════════════════════════════════════
// Custom Log Levels
// ═══════════════════════════════════════════════════════════════
const ASTRA_LEVELS = {
  levels: {
    error:    0,
    warn:     1,
    info:     2,
    preflight:3,   // Custom — preflight health check logs
    astar:    4,   // Custom — A* engine logs
    codegen:  5,   // Custom — code generation logs
    debug:    6,
  },
  colors: {
    error:     "red",
    warn:      "yellow",
    info:      "cyan",
    preflight: "magenta",
    astar:     "blue",
    codegen:   "green",
    debug:     "gray",
  },
};

winston.addColors(ASTRA_LEVELS.colors);

// ═══════════════════════════════════════════════════════════════
// Log Format — Console (colored + readable)
// ═══════════════════════════════════════════════════════════════
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: "YYYY-MM-DD HH:mm:ss" }),
  winston.format.colorize({ all: true }),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    const metaStr = Object.keys(meta).length
      ? `\n  ${JSON.stringify(meta, null, 2)}`
      : "";
    return `[${timestamp}] [ASTRA] [${level.toUpperCase()}] ${message}${metaStr}`;
  })
);

// ═══════════════════════════════════════════════════════════════
// Log Format — File (clean JSON for parsing)
// ═══════════════════════════════════════════════════════════════
const fileFormat = winston.format.combine(
  winston.format.timestamp({ format: "YYYY-MM-DD HH:mm:ss" }),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

// ═══════════════════════════════════════════════════════════════
// Transports
// ═══════════════════════════════════════════════════════════════
const transports: winston.transport[] = [
  new winston.transports.Console({
    format: consoleFormat,
  }),
];

if (ENV.LOG_TO_FILE) {
  transports.push(
    new winston.transports.File({
      filename: logFilePath,
      format:   fileFormat,
      maxsize:  5 * 1024 * 1024,   // 5MB max log file
      maxFiles: 3,                  // Keep last 3 rotated files
    })
  );
}

// ═══════════════════════════════════════════════════════════════
// Logger Instance
// ═══════════════════════════════════════════════════════════════
const winstonLogger = winston.createLogger({
  levels:     ASTRA_LEVELS.levels,
  level:      ENV.LOG_LEVEL,
  transports,
  exitOnError: false,
});

// ═══════════════════════════════════════════════════════════════
// ASTRA Logger — typed wrapper around winston
// ═══════════════════════════════════════════════════════════════
export const logger = {

  // ─── Standard Levels ────────────────────────────────────────
  info: (message: string, meta?: Record<string, unknown>) =>
    winstonLogger.info(message, meta),

  warn: (message: string, meta?: Record<string, unknown>) =>
    winstonLogger.warn(message, meta),

  error: (message: string, meta?: Record<string, unknown>) =>
    winstonLogger.error(message, meta),

  debug: (message: string, meta?: Record<string, unknown>) =>
    winstonLogger.debug(message, meta),

  // ─── Custom ASTRA Levels ────────────────────────────────────
  preflight: (message: string, meta?: Record<string, unknown>) =>
    (winstonLogger as any).preflight(message, meta),

  astar: (message: string, meta?: Record<string, unknown>) =>
    (winstonLogger as any).astar(message, meta),

  codegen: (message: string, meta?: Record<string, unknown>) =>
    (winstonLogger as any).codegen(message, meta),

  // ─── Section Divider — clean visual separator in logs ───────
  divider: (title: string) => {
    const line = "═".repeat(60);
    winstonLogger.info(`\n${line}\n  ${title}\n${line}`);
  },

  // ─── Preflight Result Logger ─────────────────────────────────
  preflightResult: (
    analyser: string,
    status: "PASS" | "FAIL" | "WARN" | "SKIP",
    detail?: string
  ) => {
    const icon: Record<string, string> = {
      PASS: "✅",
      FAIL: "❌",
      WARN: "⚠️ ",
      SKIP: "⏭️ ",
    };
    const msg = `${icon[status]} [${analyser}] → ${status}${detail ? ` — ${detail}` : ""}`;

    if (status === "FAIL")  winstonLogger.error(msg);
    else if (status === "WARN") winstonLogger.warn(msg);
    else (winstonLogger as any).preflight(msg);
  },

  // ─── A* Step Logger ──────────────────────────────────────────
  astarStep: (
    iteration: number,
    fieldName: string,
    gScore: number,
    hScore: number,
    fScore: number
  ) => {
    (winstonLogger as any).astar(
      `Iteration ${iteration} | Field: ${fieldName} | g=${gScore} h=${hScore} f=${fScore}`
    );
  },

  // ─── Goal Reached Logger ────────────────────────────────────
  goalReached: (pathTaken: string[], totalIterations: number) => {
    winstonLogger.info(
      `🎯 GOAL REACHED in ${totalIterations} iterations | Path: ${pathTaken.join(" → ")}`
    );
  },
};

export default logger;