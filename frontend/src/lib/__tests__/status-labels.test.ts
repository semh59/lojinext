import { describe, expect, it } from "vitest";
import {
  getConfigGroupLabel,
  getTrailerTipiLabel,
  getRouteTypeLabel,
  getFuelTypeLabel,
} from "../status-labels";

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

describe("getRouteTypeLabel", () => {
  it("maps sofor_service.py's route_type keys to English", () => {
    expect(getRouteTypeLabel("highway_dominant", "en")).toBe("Highway-heavy");
    expect(getRouteTypeLabel("mountain", "en")).toBe("Mountainous");
    expect(getRouteTypeLabel("urban", "en")).toBe("Urban");
    expect(getRouteTypeLabel("mixed", "en")).toBe("Mixed");
  });

  it("matches the backend's own Turkish labels for the Turkish locale", () => {
    expect(getRouteTypeLabel("highway_dominant", "tr")).toBe(
      "Otoyol Ağırlıklı",
    );
    expect(getRouteTypeLabel("mountain", "tr")).toBe("Dağlık");
  });

  it("falls back to the raw key for an unrecognised route type", () => {
    expect(getRouteTypeLabel("unknown_type", "en")).toBe("unknown_type");
  });
});

describe("getFuelTypeLabel", () => {
  it("maps araclar.yakit_tipi values to English", () => {
    expect(getFuelTypeLabel("DIZEL", "en")).toBe("DIESEL");
    expect(getFuelTypeLabel("BENZIN", "en")).toBe("GASOLINE");
    expect(getFuelTypeLabel("ELEKTRIK", "en")).toBe("ELECTRIC");
  });

  it("keeps already-English-looking values unchanged", () => {
    expect(getFuelTypeLabel("LPG", "en")).toBe("LPG");
    expect(getFuelTypeLabel("HYBRID", "en")).toBe("HYBRID");
  });

  it("keeps Turkish labels unchanged for the Turkish locale", () => {
    expect(getFuelTypeLabel("DIZEL", "tr")).toBe("DIZEL");
  });
});
