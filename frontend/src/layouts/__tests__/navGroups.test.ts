import { describe, expect, it } from "vitest";
import i18n from "../../i18n";
import { buildNavGroups } from "../navGroups";

// Labels are now i18n-driven; resolve them through the real (tr) instance.
const t = (key: string, fallback?: string): string =>
  i18n.t(key, { defaultValue: fallback ?? "" });

describe("buildNavGroups — RV2.9 sidebar", () => {
  it("admin: Bugün + Sistem + Filo İçgörü + Strategic Cockpit görünür", () => {
    const groups = buildNavGroups({ role: "admin" }, t);

    // 1. grup (label null): Bugün
    expect(groups[0].label).toBeNull();
    expect(groups[0].items[0].label).toBe("Bugün");
    expect(groups[0].items[0].path).toBe("/today");

    // Operasyon → Bakım var
    const operasyon = groups.find((g) => g.label === "Operasyon");
    expect(operasyon).toBeDefined();
    expect(operasyon?.items.some((i) => i.path === "/maintenance")).toBe(true);

    // İçgörü grubu var + Filo İçgörü + Strategic Cockpit + Rapor Stüdyosu
    const insight = groups.find((g) => g.label === "İçgörü");
    expect(insight).toBeDefined();
    const insightPaths = insight!.items.map((i) => i.path);
    expect(insightPaths).toContain("/insights/fleet");
    expect(insightPaths).toContain("/executive");
    expect(insightPaths).toContain("/reports");

    // Sistem grubu var — Administration + Live Monitoring
    const sistem = groups.find((g) => g.label === "Sistem");
    expect(sistem).toBeDefined();
    expect(sistem?.items[0].path).toBe("/admin");
    expect(sistem?.items.map((i) => i.path)).toContain("/monitoring");
  });

  it("fleet_manager: Bugün + İçgörü görünür, Sistem yok", () => {
    const groups = buildNavGroups({ role: "fleet_manager" }, t);

    expect(groups[0].items[0].label).toBe("Bugün");
    expect(groups.find((g) => g.label === "Sistem")).toBeUndefined();

    const insight = groups.find((g) => g.label === "İçgörü");
    const insightPaths = insight!.items.map((i) => i.path);
    expect(insightPaths).toContain("/insights/fleet");
    expect(insightPaths).toContain("/executive");
  });

  it("user (non-triage): Panel görünür, Filo İçgörü ve Strategic Cockpit gizli", () => {
    const groups = buildNavGroups({ role: "user" }, t);

    // Panel (canSeeTriage=false branch)
    expect(groups[0].items[0].label).toBe("Filo Paneli");
    expect(groups[0].items[0].path).toBe("/");

    // Sistem yok
    expect(groups.find((g) => g.label === "Sistem")).toBeUndefined();

    // İçgörü grubu var ama Filo İçgörü + Strategic Cockpit GİZLİ
    const insight = groups.find((g) => g.label === "İçgörü");
    const insightPaths = insight!.items.map((i) => i.path);
    expect(insightPaths).not.toContain("/insights/fleet");
    expect(insightPaths).not.toContain("/executive");
    // Anomaliler + Koçluk + Rapor Stüdyosu yine görünür
    expect(insightPaths).toContain("/alerts");
    expect(insightPaths).toContain("/coaching");
    expect(insightPaths).toContain("/reports");
  });

  it("null user: Panel, gizli admin/triage öğeleri yok", () => {
    const groups = buildNavGroups(null, t);

    expect(groups[0].items[0].label).toBe("Filo Paneli");
    expect(groups.find((g) => g.label === "Sistem")).toBeUndefined();

    // Bakım operasyon altında her zaman var (genel kullanıcı yetkisi yetersiz değil)
    const operasyon = groups.find((g) => g.label === "Operasyon");
    expect(operasyon?.items.map((i) => i.path)).toContain("/maintenance");
  });
});
