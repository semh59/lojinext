import { describe, expect, it } from "vitest";
import { getConfigGroupLabel } from "../status-labels";

describe("getConfigGroupLabel", () => {
  it("maps known sistem_konfig groups to English", () => {
    expect(getConfigGroupLabel("rota", "en")).toBe("Route");
    expect(getConfigGroupLabel("ml", "en")).toBe("ML");
    expect(getConfigGroupLabel("anomali", "en")).toBe("Anomaly");
    expect(getConfigGroupLabel("sistem", "en")).toBe("System");
  });

  it("maps known sistem_konfig groups to Turkish", () => {
    expect(getConfigGroupLabel("rota", "tr")).toBe("Rota");
    expect(getConfigGroupLabel("sistem", "tr")).toBe("Sistem");
  });

  it("is case-insensitive on the raw DB value", () => {
    expect(getConfigGroupLabel("ROTA", "en")).toBe("Route");
  });

  it("falls back to a plain underscore-replaced string for unknown groups", () => {
    expect(getConfigGroupLabel("yeni_grup", "en")).toBe("yeni grup");
  });
});
