/**
 * 0-mock epiği re-triage (maintenance domain): NOT converted to a real
 * backend — left mocked, unlike the sibling InspectionTab conversion.
 *
 * All 3 assertions here depend on `maintenancePredictionsService.getAll()`
 * (GET /admin/maintenance/predictions), which is backed by
 * `MaintenancePredictor` (app/core/ml/maintenance_predictor.py) — a
 * domain/ML module that computes `predictable`, `predicted_date`,
 * `confidence`, `risk_level` from real bakım/arıza history + km data. That
 * seed data can only be created via direct `db_session` inserts in the
 * backend's own integration tests (see
 * app/tests/integration/test_maintenance_predictions.py`_seed_periyodik_bakim`)
 * — there is no public REST path the frontend can use to reach the same
 * state, so exact `predictable=true` vs `false` outcomes (and specific
 * dates/confidence values) aren't reproducible from here. This mirrors the
 * "Sefer seed infra is a separate domain, out of scope" call made for
 * CalibrationModal's success-path test.
 *
 * The 503 case (`MAINTENANCE_PREDICTOR_ENABLED=False`) is also not
 * reachable: it's a backend startup env var, and this epic's real backend
 * is a shared, already-running process (not ours to restart with a
 * different flag) — confirmed live via
 * `curl .../admin/maintenance/predictions` returning 200, not 503.
 *
 * The one assertion that IS backend-independent (the static risk legend)
 * doesn't gain real coverage by hitting a real backend — it renders the
 * same 4 labels regardless of `data`. Splitting it into its own
 * real-backend file would add no signal, so the whole file stays mocked.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../../test/test-utils";

vi.mock("../../../../api/maintenance-predictions", () => ({
  maintenancePredictionsService: {
    getAll: vi.fn(),
  },
}));

vi.mock("../../../../context/NotificationContext", async () => {
  const actual: any = await vi.importActual(
    "../../../../context/NotificationContext",
  );
  return { ...actual, useNotify: () => ({ notify: vi.fn() }) };
});

// FullCalendar JSDOM'da DOM API'larıyla uyumsuz olabilir; lightweight stub
vi.mock("@fullcalendar/react", () => ({
  default: ({ events }: { events: Array<{ title: string }> }) => (
    <div data-testid="fc-stub">
      {(events || []).map((e, i) => (
        <div key={i} data-testid="fc-event">
          {e.title}
        </div>
      ))}
    </div>
  ),
}));

import { maintenancePredictionsService } from "../../../../api/maintenance-predictions";
import { MaintenanceCalendar } from "../MaintenanceCalendar";

const sample = {
  arac_id: 1,
  plaka: "34 AAA 11",
  bakim_tipi: "PERIYODIK",
  predictable: true,
  predicted_date: "2026-06-20",
  days_remaining: 25,
  is_overdue: false,
  confidence: 0.84,
  risk_level: "normal" as const,
  savings_pct: 0,
  reasons: [],
};

const sample_overdue = {
  ...sample,
  arac_id: 2,
  plaka: "34 BBB 22",
  is_overdue: true,
  days_remaining: -10,
  risk_level: "overdue" as const,
};

const sample_unpredictable = {
  ...sample,
  arac_id: 3,
  plaka: "34 CCC 33",
  predictable: false,
  predicted_date: null,
  days_remaining: null,
};

describe("MaintenanceCalendar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("legend tüm risk seviyelerini gösterir", async () => {
    (
      maintenancePredictionsService.getAll as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    render(<MaintenanceCalendar />);
    await waitFor(() => screen.getByTestId("fc-stub"));
    // 4 risk seviyesi legend'de
    expect(screen.getByText("Gecikmiş")).toBeInTheDocument();
    expect(screen.getByText("Yakında")).toBeInTheDocument();
    expect(screen.getByText("Normal")).toBeInTheDocument();
    expect(screen.getByText("Düşük risk")).toBeInTheDocument();
  });

  it("predictable=true araçlar event olur, predictable=false hariç tutulur", async () => {
    (
      maintenancePredictionsService.getAll as ReturnType<typeof vi.fn>
    ).mockResolvedValue([sample, sample_overdue, sample_unpredictable]);
    render(<MaintenanceCalendar />);
    await waitFor(() => screen.getByTestId("fc-stub"));
    const events = screen.getAllByTestId("fc-event");
    // Sadece 2 predictable kayıt → 2 event
    expect(events.length).toBe(2);
    const titles = events.map((e) => e.textContent);
    expect(titles).toContain("34 AAA 11 — PERIYODIK");
    expect(titles).toContain("34 BBB 22 — PERIYODIK");
  });

  it("503 hatası → flagOff mesajı", async () => {
    (
      maintenancePredictionsService.getAll as ReturnType<typeof vi.fn>
    ).mockRejectedValue({ response: { status: 503 } });
    render(<MaintenanceCalendar />);
    await waitFor(() =>
      expect(screen.getByText(/tahmin modülü devre dışı/i)).toBeInTheDocument(),
    );
  });
});
