

async function loginToApp(page: Page): Promise<void> {
  try {
      await page.goto(ENV.LOGIN_URL, { waitUntil: "networkidle" });

      // Try common username selectors
      const loginSelectors = [
        'input[name="Login"]',
        'input[name="Login"]',
        'input[type="Login"]',
        'input[id*="Login" i]',
        'input[id*="Login" i]',
        'input[placeholder*="Login" i]',
      ];
      const passSelectors = [
        'input[name="password"]',
        'input[type="password"]',
      ];
      const submitSelectors = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Login")',
        'button:has-text("Sign in")',
      ];

      for (const sel of loginSelectors) {
        if (await page.locator(sel).isVisible().catch(() => false)) {
          await page.locator(sel).fill(ENV.APP_USERNAME);
          break;
        }
      }
      for (const sel of passSelectors) {
        if (await page.locator(sel).isVisible().catch(() => false)) {
          await page.locator(sel).fill(ENV.APP_PASSWORD);
          break;
        }
      }
      for (const sel of submitSelectors) {
        if (await page.locator(sel).isVisible().catch(() => false)) {
          await page.locator(sel).click();
          break;
        }
      }

      await page.waitForLoadState("networkidle");

    } catch (err) {
      logger.warn(`Login during reconcile had issues: ${err} — continuing`);
    }
  }