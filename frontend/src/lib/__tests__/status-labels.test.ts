import { describe, expect, it } from "vitest";
import { getConfigGroupLabel, getTrailerTipiLabel } from "../status-labels";

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

describe("getTrailerTipiLabel", () => {
  it("maps known dorseler.tipi values to English", () => {
    expect(getTrailerTipiLabel("Tenteli", "en")).toBe("Tented");
    expect(getTrailerTipiLabel("Damperli", "en")).toBe("Tipper");
    expect(getTrailerTipiLabel("Frigo", "en")).toBe("Refrigerated");
  });

  it("keeps Turkish labels unchanged for the Turkish locale", () => {
    expect(getTrailerTipiLabel("Tenteli", "tr")).toBe("Tenteli");
  });

  it("falls back to the raw value for an unrecognised type", () => {
    expect(getTrailerTipiLabel("Ozel Tip", "en")).toBe("Ozel Tip");
  });
});
