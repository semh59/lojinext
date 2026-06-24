import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("Admin foundation source guards", () => {
  it("keeps remaining admin pages on resource-only Turkish copy", () => {
    const pages = [
      {
        path: "src/pages/admin/KonfigurasyonPage.tsx",
        forbidden: /Konfigürasyon Yönetimi/i,
      },
      {
        path: "src/pages/admin/KullanicilarPage.tsx",
        forbidden: /Kullanıcılar ve Roller/i,
      },
      {
        path: "src/pages/admin/BakimPage.tsx",
        forbidden: /Bakım ve Onarım Merkezi/i,
      },
      {
        path: "src/pages/admin/VeriYonetimPage.tsx",
        forbidden: /Veri İçe Aktarım ve Rollback/i,
      },
      {
        path: "src/pages/admin/BildirimlerPage.tsx",
        forbidden: /Bildirim Yönetimi/i,
      },
      {
        path: "src/pages/admin/MLYonetimPage.tsx",
        forbidden: /ML Modelleri ve Eğitim/i,
      },
    ];

    for (const page of pages) {
      const source = readFileSync(resolve(process.cwd(), page.path), "utf-8");
      expect(source).toContain("useAdminResources");
      expect(source).not.toMatch(page.forbidden);
    }
  });
});
