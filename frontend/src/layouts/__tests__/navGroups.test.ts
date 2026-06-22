import { describe, expect, it } from "vitest";
import { buildNavGroups } from "../navGroups";

describe("buildNavGroups — RV2.9 sidebar", () => {
  it("admin: Bugün + Sistem + Filo İçgörü + Strategic Cockpit görünür", () => {
    const groups = buildNavGroups({ role: "admin" });

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

    // Sistem grubu var
    const sistem = groups.find((g) => g.label === "Sistem");
    expect(sistem).toBeDefined();
    expect(sistem?.items[0].path).toBe("/admin");
  });

  it("fleet_manager: Bugün + İçgörü görünür, Sistem yok", () => {
    const groups = buildNavGroups({ role: "fleet_manager" });

    expect(groups[0].items[0].label).toBe("Bugün");
    expect(groups.find((g) => g.label === "Sistem")).toBeUndefined();

    const insight = groups.find((g) => g.label === "İçgörü");
    const insightPaths = insight!.items.map((i) => i.path);
    expect(insightPaths).toContain("/insights/fleet");
    expect(insightPaths).toContain("/executive");
  });

  it("user (non-triage): Panel görünür, Filo İçgörü ve Strategic Cockpit gizli", () => {
    const groups = buildNavGroups({ role: "user" });

    // Panel (canSeeTriage=false branch)
    expect(groups[0].items[0].label).toBe("Panel");
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
    const groups = buildNavGroups(null);

    expect(groups[0].items[0].label).toBe("Panel");
    expect(groups.find((g) => g.label === "Sistem")).toBeUndefined();

    // Bakım operasyon altında her zaman var (genel kullanıcı yetkisi yetersiz değil)
    const operasyon = groups.find((g) => g.label === "Operasyon");
    expect(operasyon?.items.map((i) => i.path)).toContain("/maintenance");
  });
});
