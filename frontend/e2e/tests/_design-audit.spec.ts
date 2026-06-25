/* Design audit — renders current code with mocked auth/data and screenshots
 * the pages referenced in the UI review. Not part of the assertion suite;
 * run explicitly:  npx playwright test _design-audit --project=chromium
 */
import { test } from "@playwright/test";

const OUT = "e2e/reports/design-audit";

function json(body: unknown) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  };
}

const USER = {
  id: 1,
  kullanici_adi: "admin",
  username: "admin",
  ad_soyad: "Admin User",
  full_name: "Admin User",
  rol: { ad: "super_admin", yetkiler: { "*": true } },
  role: "super_admin",
  aktif: true,
  is_active: true,
};

// Realistic laptop viewport so any "cut off" / overflow shows in screenshots.
test.use({ viewport: { width: 1366, height: 768 } });

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("access_token", "audit-fake-token");
  });
  // websockets off (monitoring/notifications keep retrying otherwise)
  await page.route("**/api/v1/ws/**", (r) => r.abort());
  await page.route("**/ws/**", (r) => r.abort());
  await page.route("**/auth/me", (r) => r.fulfill(json(USER)));
  // LIFO: catch-all FIRST (lowest priority), specifics AFTER (win).
  await page.route("**/api/v1/**", (r) =>
    r.fulfill(json({ items: [], total: 0, results: [], data: [] })),
  );
  // array-returning endpoints (object would crash .map on the audited pages)
  await page.route("**/api/v1/admin/maintenance/alerts**", (r) => r.fulfill(json([])));
  await page.route("**/api/v1/admin/maintenance/predictions**", (r) =>
    r.fulfill(json([])),
  );
  await page.route("**/api/v1/vehicles/inspection-alerts**", (r) =>
    r.fulfill(
      json({
        expiring: [
          { id: 1, plaka: "34 ABC 03", marka: "Mercedes", model: "Actros", muayene_tarihi: "2026-07-12", days_remaining: 17 },
        ],
        overdue: [
          { id: 2, plaka: "06 XYZ 99", marka: "Volvo", model: "FH16", muayene_tarihi: "2026-06-10", days_remaining: -15 },
        ],
      }),
    ),
  );
  await page.route("**/api/v1/trailers/inspection-alerts**", (r) =>
    r.fulfill(
      json({
        expiring: [
          { id: 5, plaka: "34 DRS 01", marka: "Kassbohrer", tipi: "Tenteli", muayene_tarihi: "2026-07-20", days_remaining: 25 },
        ],
        overdue: [],
      }),
    ),
  );
  await page.route("**/api/v1/errors/**", (r) => r.fulfill(json([])));
  await page.route("**/api/v1/monitoring/**", (r) => r.fulfill(json([])));
  await page.route("**/api/v1/vehicles**", (r) =>
    r.fulfill(
      json({
        items: [{ id: 3, plaka: "34 ABC 03", marka: "Mercedes", aktif: true }],
        total: 1,
      }),
    ),
  );
  await page.route("**/api/v1/trailers**", (r) =>
    r.fulfill(json({ items: [], total: 0 })),
  );
});

async function snap(page: import("@playwright/test").Page, path: string, name: string, full = true) {
  await page.goto(path);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
}

test("design audit screenshots", async ({ page }) => {
  // main app sidebar (lang/theme buttons, "Bakım" nav item)
  await snap(page, "/today", "01-main-sidebar", false);
  // admin panel (admin sidebar items — is "Bakım" shortcut here?)
  await snap(page, "/admin", "02-admin-overview", true);
  // bakım page (muayene to be added; general layout)
  await snap(page, "/maintenance", "03-bakim", true);
  // new Muayene (inspection) tab — vehicles + trailers
  await snap(page, "/maintenance?view=muayene", "03b-muayene", true);
  // new "Arıza Bildir" quick-report modal
  await page.goto("/maintenance");
  await page.waitForTimeout(1200);
  const reportBtn = page.getByRole("button", { name: /Arıza Bildir/i }).first();
  if (await reportBtn.count()) {
    await reportBtn.click();
    await page.waitForTimeout(700);
    await page.screenshot({ path: `${OUT}/03c-ariza-bildir.png` });
  }
  // live error page
  await snap(page, "/monitoring", "04-monitoring", true);
  // admin "similar" error/health page
  await snap(page, "/admin/saglik", "05-admin-saglik", true);
  // admin notifications (another candidate for the error merge)
  await snap(page, "/admin/bildirimler", "06-admin-bildirimler", true);
  // fleet (vehicle add modal)
  await page.goto("/fleet");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/07-fleet.png`, fullPage: false });
  const addV = page.getByRole("button", { name: /Yeni Araç Ekle/i }).first();
  if (await addV.count()) {
    await addV.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/08-vehicle-modal.png` }); // viewport => cutoff visible
  }
  // trailers add modal — try a trailers tab/button on the same page
  const tabTrailers = page.getByRole("tab", { name: /Dorse|Trailer/i }).first();
  if (await tabTrailers.count()) {
    await tabTrailers.click();
    await page.waitForTimeout(600);
  }
  const addT = page.getByRole("button", { name: /Yeni Dorse Ekle/i }).first();
  if (await addT.count()) {
    await addT.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/09-trailer-modal.png` });
  }
});
