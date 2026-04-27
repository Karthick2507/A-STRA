// ═══════════════════════════════════════════════════════════════
// preflight/domAnalyser.ts  (v4 — clean rewrite)
// ASTRA Framework — DOM Analyser
// ═══════════════════════════════════════════════════════════════

import { chromium, Browser, Page } from "@playwright/test";
import { ENV }    from "../utils/envLoader";
import { logger } from "../utils/logger";
import { AnalyserResult } from "../utils/reportGenerator";
import * as fs   from "fs-extra";
import * as path from "path";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export interface DomField {
  name:         string;
  id:           string;
  type:         string;
  label:        string;
  placeholder:  string;
  required:     boolean;
  selector:     string;
  options?:     string[];
  pattern?:     string;
  minLength?:   number;
  maxLength?:   number;
  min?:         string;
  max?:         string;
  section?:     string;
  stepIndex?:   number;
  visible:      boolean;
  tagName:      string;
  indexOnPage:  number;
}

export interface DomAnalyserFindings {
  totalFields:    number;
  requiredFields: number;
  optionalFields: number;
  isMultiStep:    boolean;
  totalSteps:     number;
  hasFieldsets:   boolean;
  fields:         DomField[];
  pageTitle:      string;
  formCount:      number;
}

// ═══════════════════════════════════════════════════════════════
// runDomAnalyser
// ═══════════════════════════════════════════════════════════════
export async function runDomAnalyser(): Promise<AnalyserResult> {
  const start = Date.now();
  const name  = "DOM Analyser";
  const diagDir = path.resolve(process.cwd(), "reports/preflight");

  logger.divider("DOM Analyser — Starting");
  await fs.ensureDir(diagDir);

  if (!ENV.DOM_ANALYSER_ENABLED) {
    return buildResult(name, "SKIP", Date.now() - start, "Disabled in config", {});
  }

  // ── STEP 0: ENV guard ─────────────────────────────────────────
  logger.preflight("─── ENV Check ──────────────────────────────────────");
  logger.preflight(`  LOGIN_URL       : ${ENV.LOGIN_URL       || "❌ EMPTY"}`);
  logger.preflight(`  TARGET_PAGE_URL : ${ENV.TARGET_PAGE_URL || "❌ EMPTY"}`);
  logger.preflight(`  APP_USERNAME    : ${ENV.APP_USERNAME    ? ENV.APP_USERNAME.substring(0,6)+"***" : "❌ EMPTY"}`);
  logger.preflight(`  APP_PASSWORD    : ${ENV.APP_PASSWORD    ? "***set***" : "❌ EMPTY"}`);
  logger.preflight(`  HEADLESS        : ${ENV.HEADLESS}`);
  logger.preflight("────────────────────────────────────────────────────");

  const missing = [
    !ENV.LOGIN_URL       && "LOGIN_URL",
    !ENV.TARGET_PAGE_URL && "TARGET_PAGE_URL",
    !ENV.APP_USERNAME    && "APP_USERNAME",
    !ENV.APP_PASSWORD    && "APP_PASSWORD",
  ].filter(Boolean) as string[];

  if (missing.length > 0) {
    logger.error(`❌ Missing .env keys: ${missing.join(", ")}`);
    return buildResult(name, "FAIL", Date.now() - start,
      `Missing .env keys: ${missing.join(", ")}`, { missing });
  }

  let browser: Browser | null = null;

  try {
    // ── STEP 1: Launch ────────────────────────────────────────────
    logger.preflight("STEP 1: Launching browser...");
    browser = await chromium.launch({ headless: ENV.HEADLESS, slowMo: 0 });
    const page = await browser.newPage();
    await page.setViewportSize({ width: 1440, height: 900 });
    page.setDefaultTimeout(20000);
    logger.preflight("STEP 1: ✅ Browser launched");

    // ── STEP 2: Login ─────────────────────────────────────────────
    logger.preflight(`STEP 2: Logging in → ${ENV.LOGIN_URL}`);
    await loginToApp(page);
    logger.preflight(`STEP 2: ✅ Post-login URL: ${page.url()}`);

    // ── STEP 3: Navigate to target ────────────────────────────────
    logger.preflight(`STEP 3: Navigating → ${ENV.TARGET_PAGE_URL}`);
    await page.goto(ENV.TARGET_PAGE_URL, {
      waitUntil: "domcontentloaded",
      timeout:   25000,
    });
    logger.preflight(`STEP 3: ✅ Arrived at: ${page.url()}`);

    // ── STEP 4: SPA hydration wait ────────────────────────────────
    logger.preflight("STEP 4: Waiting 5s for React/SPA to render...");
    await page.waitForTimeout(5000);

    // ── STEP 4b: Trigger React rendering via interaction ──────────
    // React/SPA apps sometimes only fully render after a user event
    logger.preflight("STEP 4b: Triggering page interaction to force React render...");
    try {
      // Move mouse to centre of page — triggers React synthetic events
      await page.mouse.move(720, 450);
      await page.waitForTimeout(500);
      // Click somewhere safe (not a button) to trigger focus events
      await page.mouse.click(720, 450);
      await page.waitForTimeout(500);
      // Scroll slightly — triggers IntersectionObserver
      await page.keyboard.press("Tab");
      await page.waitForTimeout(1000);
    } catch { /* non-critical */ }

    logger.preflight("STEP 4b: Interaction done — waiting another 2s...")
    await page.waitForTimeout(2000);

    // ── STEP 5: Diagnostic counts ─────────────────────────────────
    const counts = await page.evaluate(() => ({
      input:       document.querySelectorAll("input").length,
      select:      document.querySelectorAll("select").length,
      textarea:    document.querySelectorAll("textarea").length,
      allEls:      document.querySelectorAll("*").length,
      forms:       document.querySelectorAll("form").length,
      iframes:     document.querySelectorAll("iframe").length,
      combobox:    document.querySelectorAll("[role='combobox']").length,
      textbox:     document.querySelectorAll("[role='textbox']").length,
      url:         window.location.href,
      title:       document.title,
      bodyLen:     document.body?.innerHTML?.length ?? 0,
    }));

    logger.preflight("─── DOM Diagnostic ─────────────────────────────────");
    logger.preflight(`  URL       : ${counts.url}`);
    logger.preflight(`  Title     : ${counts.title}`);
    logger.preflight(`  Body len  : ${counts.bodyLen} chars`);
    logger.preflight(`  Total els : ${counts.allEls}`);
    logger.preflight(`  input     : ${counts.input}`);
    logger.preflight(`  select    : ${counts.select}`);
    logger.preflight(`  textarea  : ${counts.textarea}`);
    logger.preflight(`  form      : ${counts.forms}`);
    logger.preflight(`  iframe    : ${counts.iframes}`);
    logger.preflight(`  combobox  : ${counts.combobox}`);
    logger.preflight(`  textbox   : ${counts.textbox}`);
    logger.preflight("────────────────────────────────────────────────────");

    // ── STEP 6: Screenshot + HTML ─────────────────────────────────
    await page.screenshot({ path: path.join(diagDir, "dom_snapshot.png"), fullPage: true });
    await fs.writeFile(path.join(diagDir, "dom_snapshot.html"), await page.content());
    logger.preflight("STEP 6: ✅ dom_snapshot.png + dom_snapshot.html saved");

    // ── STEP 7: Scroll to reveal lazy fields ─────────────────────
    logger.preflight("STEP 7: Scrolling to reveal lazy fields...");
    await scrollFullPage(page);

    // ── STEP 8: Wait for inputs ───────────────────────────────────
    logger.preflight("STEP 8: Waiting for any input...");
    await waitForAnyInput(page, 8000);

    // ── STEP 9: Scan ──────────────────────────────────────────────
    logger.preflight("STEP 9: Running field scan...");
    const findings = await scanPage(page);
    logger.preflight(`STEP 9: ✅ Scan done — ${findings.totalFields} fields`);

    // ── Save findings ─────────────────────────────────────────────
    if (findings.totalFields > 0) {
      const outPath = path.join(diagDir, "domFindings.json");
      await fs.writeJson(outPath, findings, { spaces: 2 });
      logger.preflight(`💾 Findings saved → ${outPath}`);

      logger.preflight("─── Detected Fields ──────────────────────────────");
      findings.fields.forEach((f, i) => {
        logger.preflight(`  [${i+1}] "${f.label}" name="${f.name}" type=${f.type} required=${f.required} selector="${f.selector}"`);
      });
      logger.preflight("──────────────────────────────────────────────────");
    }

    if (findings.totalFields === 0) {
      logger.preflight("⚠️  Zero fields — open reports/preflight/dom_snapshot.png to see the page state");
      return buildResult(name, "WARN", Date.now() - start,
        "No fields detected — see reports/preflight/dom_snapshot.png",
        findings as unknown as Record<string,unknown>);
    }

    logger.preflightResult(name, "PASS", `${findings.totalFields} fields mapped`);
    return buildResult(name, "PASS", Date.now() - start,
      `${findings.totalFields} fields (${findings.requiredFields} required)`,
      findings as unknown as Record<string,unknown>);

  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.error(`DOM Analyser crash: ${msg}`);
    // Try to save screenshot even on crash
    try {
      if (browser) {
        const pages = browser.contexts()[0]?.pages() ?? [];
        if (pages[0]) {
          await pages[0].screenshot({ path: path.join(diagDir, "crash_snapshot.png") }).catch(() => {});
          logger.preflight("💾 Crash screenshot → reports/preflight/crash_snapshot.png");
        }
      }
    } catch { /* ignore */ }
    return buildResult(name, "FAIL", Date.now() - start, msg, { error: msg });
  } finally {
    if (browser) await browser.close();
  }
}

// ═══════════════════════════════════════════════════════════════
// waitForAnyInput — tries every strategy to find at least one field
// ═══════════════════════════════════════════════════════════════
async function waitForAnyInput(page: Page, timeoutMs: number): Promise<boolean> {

  // Strategy 1: Playwright getByRole — most React-aware method
  // This uses ARIA tree — works even when CSS selector finds nothing
  logger.preflight("  Trying getByRole('textbox')...");
  try {
    await page.getByRole("textbox").first().waitFor({ state: "visible", timeout: 5000 });
    const count = await page.getByRole("textbox").count();
    logger.preflight(`  ✅ getByRole textbox found ${count} fields`);
    return true;
  } catch { logger.preflight("  textbox role: none found"); }

  // Strategy 2: getByRole combobox (dropdowns)
  logger.preflight("  Trying getByRole('combobox')...");
  try {
    await page.getByRole("combobox").first().waitFor({ state: "visible", timeout: 3000 });
    const count = await page.getByRole("combobox").count();
    logger.preflight(`  ✅ getByRole combobox found ${count} fields`);
    return true;
  } catch { logger.preflight("  combobox role: none found"); }

  // Strategy 3: standard CSS selectors
  const cssSelectors = [
    "input:not([type='hidden']):not([type='submit'])",
    "textarea",
    "select",
    "[role='textbox']",
    "[role='combobox']",
    "[contenteditable='true']",
  ];

  for (const sel of cssSelectors) {
    try {
      await page.waitForSelector(sel, { state: "visible", timeout: 2000 });
      logger.preflight(`  ✅ CSS selector found: ${sel}`);
      return true;
    } catch { /* try next */ }
  }

  // Strategy 4: page.$$eval count — bypasses visibility requirement
  logger.preflight("  Trying raw count via $$eval...");
  try {
    const count = await page.$$eval(
      "input, textarea, select, [role='textbox'], [role='combobox']",
      els => els.length
    );
    logger.preflight(`  $$eval found ${count} elements (including hidden)`);
    if (count > 0) return true;
  } catch { /* ignore */ }

  return false;
}

// ═══════════════════════════════════════════════════════════════
// scrollFullPage
// ═══════════════════════════════════════════════════════════════
async function scrollFullPage(page: Page): Promise<void> {
  try {
    await page.evaluate(async () => {
      const h = document.body.scrollHeight;
      for (let y = 0; y < h; y += 200) {
        window.scrollTo(0, y);
        await new Promise(r => setTimeout(r, 60));
      }
      window.scrollTo(0, 0);
    });
    await page.waitForTimeout(600);
  } catch { /* non-critical */ }
}

// ═══════════════════════════════════════════════════════════════
// scanPage — Playwright-native scan
// Uses page.locator() which is more reliable than page.evaluate()
// for React/SPA apps where fields may not appear in raw DOM yet
// ═══════════════════════════════════════════════════════════════
async function scanPage(page: Page): Promise<DomAnalyserFindings> {

  // ── First: dump raw HTML so we can see actual structure ──────
  const diagDir  = path.resolve(process.cwd(), "reports/preflight");
  const bodyHtml = await page.evaluate(() => document.body.innerHTML);
  await fs.writeFile(path.join(diagDir, "body_dump.html"), bodyHtml);
  logger.preflight(`  HTML dump → reports/preflight/body_dump.html (${bodyHtml.length} chars)`);

  // ── Log first 800 chars of body so we can see structure ──────
  logger.preflight(`  Body preview: ${bodyHtml.substring(0, 800).replace(/\n/g, " ")}`);

  // ── Use Playwright locators — handles React virtual DOM ──────
  const fields: DomField[] = [];
  const seen   = new Set<string>();

  // ── STRATEGY A: getByRole — Playwright's most powerful locator
  // Works via ARIA accessibility tree — sees React components
  // that CSS selectors completely miss
  logger.preflight("  Strategy A: Scanning via getByRole (ARIA tree)...");
  try {
    const textboxCount  = await page.getByRole("textbox").count();
    const comboboxCount = await page.getByRole("combobox").count();
    const spinCount     = await page.getByRole("spinbutton").count();
    const checkCount    = await page.getByRole("checkbox").count();
    const radioCount    = await page.getByRole("radio").count();

    logger.preflight(`    textbox:${textboxCount} combobox:${comboboxCount} spinbutton:${spinCount} checkbox:${checkCount} radio:${radioCount}`);

    const roleGroups: Array<{ role: string; type: string }> = [
      { role: "textbox",    type: "text"     },
      { role: "combobox",   type: "dropdown" },
      { role: "spinbutton", type: "number"   },
      { role: "checkbox",   type: "checkbox" },
      { role: "radio",      type: "radio"    },
    ];

    for (const { role, type } of roleGroups) {
      const locator = page.getByRole(role as any);
      const count   = await locator.count();
      if (count === 0) continue;

      for (let i = 0; i < count; i++) {
        const el      = locator.nth(i);
        const visible = await el.isVisible().catch(() => false);
        if (!visible) continue;

        const id          = await el.getAttribute("id")          ?? "";
        const name        = await el.getAttribute("name")        ?? "";
        const placeholder = await el.getAttribute("placeholder") ?? "";
        const ariaLabel   = await el.getAttribute("aria-label")  ?? "";
        const required    = await el.getAttribute("required")    !== null ||
                            await el.getAttribute("aria-required") === "true";
        const tagName     = await el.evaluate((e: Element) => e.tagName.toLowerCase());

        // Get accessible name — Playwright knows this natively
        const accessibleName = await el.evaluate((e: Element) => {
          // 1. aria-labelledby
          const lblBy = e.getAttribute("aria-labelledby");
          if (lblBy) {
            const lblEl = document.getElementById(lblBy);
            if (lblEl) return lblEl.textContent?.replace(/\*/g,"").trim() ?? "";
          }
          // 2. aria-label
          const al = e.getAttribute("aria-label");
          if (al) return al.trim();
          // 3. label[for]
          const id2 = e.getAttribute("id");
          if (id2) {
            const lbl = document.querySelector(`label[for="${id2}"]`);
            if (lbl) return lbl.textContent?.replace(/\*/g,"").trim() ?? "";
          }
          // 4. Closest label
          const parentLbl = e.closest("label");
          if (parentLbl) return parentLbl.textContent?.replace(/\*/g,"").trim() ?? "";
          // 5. Sibling scan — Freewheel MRM pattern
          let parent = e.parentElement;
          let depth  = 0;
          while (parent && depth < 8) {
            const kids  = Array.from(parent.children);
            const myEl  = kids.find(c => c === e || c.contains(e));
            const myIdx = myEl ? kids.indexOf(myEl) : -1;
            for (let j = myIdx - 1; j >= 0; j--) {
              const sib  = kids[j];
              const text = sib.textContent?.replace(/\*/g,"").trim() ?? "";
              if (text.length >= 2 && text.length <= 100 &&
                  !sib.querySelector("input,select,textarea")) {
                const t = sib.tagName.toLowerCase();
                if (!["script","style","svg"].includes(t)) return text;
              }
            }
            parent = parent.parentElement;
            depth++;
          }
          // 6. placeholder
          return (e as HTMLInputElement).placeholder?.trim() ?? "";
        }).catch(() => "");

        const rawName  = name || ariaLabel || accessibleName || placeholder || `field_${fields.length+1}`;
        const fieldName = rawName
          .toLowerCase()
          .replace(/[^a-z0-9\s]/g, " ")
          .trim()
          .replace(/\s+/g, "_")
          .substring(0, 40) || `field_${fields.length+1}`;

        if (seen.has(fieldName)) continue;
        seen.add(fieldName);

        const selector = id          ? `#${id}`
                       : name        ? `[name="${name}"]`
                       : ariaLabel   ? `[aria-label="${ariaLabel}"]`
                       : placeholder ? `${tagName}[placeholder="${placeholder}"]`
                       : `[role="${role}"]:nth-of-type(${i+1})`;

        fields.push({
          name:        fieldName,
          id,
          type,
          label:       accessibleName || rawName,
          placeholder,
          required,
          selector,
          section:     "default",
          stepIndex:   0,
          visible:     true,
          tagName,
          indexOnPage: fields.length,
        });

        logger.preflight(`    [${fields.length}] role=${role} label="${accessibleName || rawName}" name="${fieldName}" sel="${selector}"`);
      }
    }
  } catch (err) {
    logger.preflight(`  Strategy A error: ${err}`);
  }

  logger.preflight(`  Strategy A found: ${fields.length} fields`);

  // ── STRATEGY B: CSS selectors — fallback if getByRole finds nothing
  logger.preflight(`  Strategy B: CSS selector scan (fallback)...`);

  // All input-like selectors to try
  const inputSelectors: Array<{ sel: string; type: string }> = [
    { sel: "input[type='text']",     type: "text"     },
    { sel: "input[type='email']",    type: "email"    },
    { sel: "input[type='password']", type: "password" },
    { sel: "input[type='number']",   type: "number"   },
    { sel: "input[type='tel']",      type: "phone"    },
    { sel: "input[type='date']",     type: "date"     },
    { sel: "input[type='url']",      type: "url"      },
    { sel: "input:not([type])",      type: "text"     },
    { sel: "input[type='search']",   type: "text"     },
    { sel: "textarea",               type: "textarea" },
    { sel: "select",                 type: "dropdown" },
    { sel: "[role='textbox']",       type: "text"     },
    { sel: "[role='combobox']",      type: "dropdown" },
    { sel: "[role='spinbutton']",    type: "number"   },
    { sel: "[contenteditable='true']", type: "text"   },
  ];

  let idx = 0;
  for (const { sel, type } of inputSelectors) {
    try {
      const locator = page.locator(sel);
      const count   = await locator.count();

      if (count === 0) continue;
      logger.preflight(`  Found ${count} elements for: ${sel}`);

      for (let i = 0; i < count; i++) {
        const el = locator.nth(i);

        // Skip if not visible
        const visible = await el.isVisible().catch(() => false);
        if (!visible) continue;

        // Get attributes
        const id          = await el.getAttribute("id")          ?? "";
        const name        = await el.getAttribute("name")        ?? "";
        const placeholder = await el.getAttribute("placeholder") ?? "";
        const ariaLabel   = await el.getAttribute("aria-label")  ?? "";
        const required    = await el.getAttribute("required")    !== null ||
                            await el.getAttribute("aria-required") === "true";
        const tagName     = await el.evaluate(e => e.tagName.toLowerCase());

        // Get label using proximity — look at surrounding DOM
        const label = await el.evaluate((el: Element) => {
          // 1. Standard label[for]
          const id2 = el.getAttribute("id");
          if (id2) {
            const lbl = document.querySelector(`label[for="${id2}"]`);
            if (lbl) return lbl.textContent?.replace(/\*/g,"").trim() ?? "";
          }

          // 2. aria-label
          const al = el.getAttribute("aria-label");
          if (al) return al.trim();

          // 3. Walk up DOM — find text sibling ABOVE this element
          let parent = el.parentElement;
          let depth  = 0;
          while (parent && depth < 8) {
            const children = Array.from(parent.children);
            const myEl     = children.find(c => c === el || c.contains(el));
            const myIdx    = myEl ? children.indexOf(myEl) : -1;

            for (let j = myIdx - 1; j >= 0; j--) {
              const sib  = children[j];
              const text = sib.textContent?.replace(/\*/g,"").trim() ?? "";
              // Skip empty, too long, or elements containing inputs
              if (text.length >= 2 && text.length <= 100 &&
                  !sib.querySelector("input,select,textarea")) {
                // Make sure it's a text-bearing element
                const tag = sib.tagName.toLowerCase();
                if (!["script","style","svg"].includes(tag)) {
                  return text;
                }
              }
            }
            parent = parent.parentElement;
            depth++;
          }

          // 4. placeholder
          return (el as HTMLInputElement).placeholder?.trim() ?? "";
        }).catch(() => "");

        // Build field name from: name attr → aria-label → label text → index
        const rawName = name || ariaLabel || label || placeholder || `field_${idx+1}`;
        const fieldName = rawName
          .toLowerCase()
          .replace(/[^a-z0-9\s]/g, " ")
          .trim()
          .replace(/\s+/g, "_")
          .substring(0, 40) || `field_${idx+1}`;

        // Skip duplicates
        if (seen.has(fieldName)) continue;
        seen.add(fieldName);

        // Build selector — most specific first
        const selector = id          ? `#${id}`
                       : name        ? `[name="${name}"]`
                       : ariaLabel   ? `[aria-label="${ariaLabel}"]`
                       : placeholder ? `${tagName}[placeholder="${placeholder}"]`
                       : `${sel}:nth-of-type(${i+1})`;

        // Get dropdown options if select
        const options: string[] = tagName === "select"
          ? await el.evaluate(e => Array.from((e as HTMLSelectElement).options)
              .map(o => o.text.trim())
              .filter(t => t && !t.toLowerCase().startsWith("select")))
          : [];

        fields.push({
          name:        fieldName,
          id,
          type,
          label:       label || rawName,
          placeholder,
          required,
          selector,
          options:     options.length > 0 ? options : undefined,
          section:     "default",
          stepIndex:   0,
          visible:     true,
          tagName,
          indexOnPage: idx,
        });

        idx++;
        logger.preflight(`    [${idx}] "${label || rawName}" → name="${fieldName}" sel="${selector}" required=${required}`);
      }
    } catch (err) {
      logger.preflight(`  Selector "${sel}" error: ${err}`);
    }
  }

  const required = fields.filter(f => f.required).length;

  return {
    totalFields:    fields.length,
    requiredFields: required,
    optionalFields: fields.length - required,
    isMultiStep:    false,
    totalSteps:     1,
    hasFieldsets:   false,
    fields,
    pageTitle:      await page.title(),
    formCount:      await page.locator("form").count(),
  };
}

// ═══════════════════════════════════════════════════════════════
// loginToApp
// ═══════════════════════════════════════════════════════════════
async function loginToApp(page: Page): Promise<void> {
  try {
    await page.goto(ENV.LOGIN_URL, { waitUntil: "domcontentloaded", timeout: 20000 });
  } catch (e) { logger.warn(`  Login page goto: ${e}`); }

  await page.waitForTimeout(2000);
  logger.preflight(`  Login page URL: ${page.url()}`);

  const userSels = [
    'input[name="Login"]',
        'input[name="Login"]',
        'input[type="Login"]',
        'input[id*="Login" i]',
        'input[id*="Login" i]',
        'input[placeholder*="Login" i]',
  ];
  const passSels = [
    'input[name="password"]','input[type="password"]','input[id*="pass" i]',
  ];
  const submitSels = [
    'button[type="submit"]','input[type="submit"]',
    'button:has-text("Login")','button:has-text("Sign in")',
    'button:has-text("Log in")','button:has-text("Sign In")',
  ];

  let filled = false;
  for (const sel of userSels) {
    try {
      if (await page.locator(sel).isVisible({ timeout: 2000 })) {
        await page.locator(sel).fill(ENV.APP_USERNAME);
        logger.preflight(`  ✅ Username → ${sel}`);
        filled = true; break;
      }
    } catch {}
  }
  if (!filled) logger.warn("  ⚠️  Username field not found");

  filled = false;
  for (const sel of passSels) {
    try {
      if (await page.locator(sel).isVisible({ timeout: 2000 })) {
        await page.locator(sel).fill(ENV.APP_PASSWORD);
        logger.preflight(`  ✅ Password → ${sel}`);
        filled = true; break;
      }
    } catch {}
  }
  if (!filled) logger.warn("  ⚠️  Password field not found");

  filled = false;
  for (const sel of submitSels) {
    try {
      if (await page.locator(sel).isVisible({ timeout: 2000 })) {
        await page.locator(sel).click();
        logger.preflight(`  ✅ Submit → ${sel}`);
        filled = true; break;
      }
    } catch {}
  }
  if (!filled) {
    logger.warn("  ⚠️  Submit button not found — pressing Enter");
    await page.keyboard.press("Enter");
  }

  await page.waitForLoadState("domcontentloaded").catch(() => {});
  await page.waitForTimeout(3000);
  logger.preflight(`  Post-login URL: ${page.url()}`);
}

// ═══════════════════════════════════════════════════════════════
// buildResult
// ═══════════════════════════════════════════════════════════════
function buildResult(
  name: string, status: AnalyserResult["status"],
  duration: number, details: string,
  findings: Record<string,unknown>
): AnalyserResult {
  return { name, status, duration, details, findings, timestamp: new Date().toISOString() };
}