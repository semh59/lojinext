import { describe, expect, it } from "vitest";
import {
  getConfigGroupLabel,
  getTrailerTipiLabel,
  getRouteTypeLabel,
  getFuelTypeLabel,
  formatMaintenanceReason,
  getMlTaskStatusMeta,
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

describe("formatMaintenanceReason", () => {
  it("formats each arac_repo.py reason code in English", () => {
    expect(
      formatMaintenanceReason(
        { code: "old_vehicle", params: { age: 18 } },
        "en-US",
      ),
    ).toBe("Old vehicle (18 yr)");
    expect(
      formatMaintenanceReason(
        { code: "high_consumption", params: { value: 37.2 } },
        "en-US",
      ),
    ).toBe("High consumption (37.2 L/100km)");
    expect(
      formatMaintenanceReason(
        { code: "high_mileage", params: { km: 523000 } },
        "en-US",
      ),
    ).toBe("High mileage (523,000 km)");
    expect(
      formatMaintenanceReason(
        { code: "no_maintenance_record", params: {} },
        "en-US",
      ),
    ).toBe("No maintenance record");
    expect(
      formatMaintenanceReason(
        { code: "overdue_maintenance", params: { days: 400 } },
        "en-US",
      ),
    ).toBe("Last maintenance 400 days ago");
  });

  it("formats the same codes in Turkish", () => {
    expect(
      formatMaintenanceReason(
        { code: "old_vehicle", params: { age: 18 } },
        "tr-TR",
      ),
    ).toBe("Yaşlı araç (18 yıl)");
    expect(
      formatMaintenanceReason(
        { code: "no_maintenance_record", params: {} },
        "tr-TR",
      ),
    ).toBe("Bakım kaydı yok");
  });

  it("falls back to the raw code for an unrecognised reason", () => {
    expect(
      formatMaintenanceReason({ code: "unknown_reason", params: {} }, "en-US"),
    ).toBe("unknown_reason");
  });
});

describe("getMlTaskStatusMeta", () => {
  it("maps ml_service.py's task durum values to English", () => {
    expect(getMlTaskStatusMeta("COMPLETED", "en").label).toBe("Completed");
    expect(getMlTaskStatusMeta("RUNNING", "en").label).toBe("Running");
    expect(getMlTaskStatusMeta("FAILED", "en").label).toBe("Failed");
    expect(getMlTaskStatusMeta("WAITING", "en").label).toBe("Waiting");
  });

  it("maps the same values to Turkish", () => {
    expect(getMlTaskStatusMeta("COMPLETED", "tr").label).toBe("Tamamlandı");
    expect(getMlTaskStatusMeta("FAILED", "tr").label).toBe("Başarısız");
  });

  it("is case-insensitive on the raw durum value", () => {
    expect(getMlTaskStatusMeta("completed", "en").label).toBe("Completed");
  });

  it("falls back to the raw value for an unrecognised status", () => {
    expect(getMlTaskStatusMeta("unknown_status", "en").label).toBe(
      "unknown_status",
    );
  });
});
