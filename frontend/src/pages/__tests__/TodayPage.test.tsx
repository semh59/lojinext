import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../test/test-utils";

vi.mock("../../api/today", () => ({
  todayService: { getTriage: vi.fn() },
}));

import { todayService } from "../../api/today";
import TodayPage from "../TodayPage";

const sampleResponse = {
  critical_count: 1,
  pending_count: 2,
  items: [
    {
      id: "anomaly:1",
      category: "anomaly" as const,
      severity: "critical" as const,
      title: "Yakıt sapma %45",
      subtitle: "critical test",
      timestamp: new Date().toISOString(),
      plaka: "34 CRT 1",
      actions: [
        {
          label: "İncele",
          url: "/alerts?id=1",
          action_type: "navigate" as const,
        },
      ],
    },
    {
      id: "maintenance:2",
      category: "maintenance" as const,
      severity: "high" as const,
      title: "PERIYODIK bakım 3 gün kaldı",
      subtitle: "",
      timestamp: new Date().toISOString(),
      plaka: "34 MNT 2",
      actions: [],
    },
    {
      id: "investigation:3",
      category: "investigation" as const,
      severity: "medium" as const,
      title: "Soruşturma",
      subtitle: "",
      timestamp: new Date().toISOString(),
      plaka: null,
      actions: [],
    },
  ],
  active_trips_count: 23,
  completed_today_count: 12,
  computed_at: new Date().toISOString(),
};

describe("TodayPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("happy path — counter ve 3 item görünür", async () => {
    (todayService.getTriage as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleResponse,
    );

    render(<TodayPage />);
    await waitFor(() =>
      expect(screen.getByText("Yakıt sapma %45")).toBeInTheDocument(),
    );
    expect(screen.getByText("PERIYODIK bakım 3 gün kaldı")).toBeInTheDocument();
    expect(screen.getByText("23")).toBeInTheDocument(); // active
    expect(screen.getByText("✓ 12")).toBeInTheDocument(); // completed
  });

  it("tab switch — Bakım sekmesine geçince anomali görünmez", async () => {
    (todayService.getTriage as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleResponse,
    );

    render(<TodayPage />);
    await waitFor(() => screen.getByText("Yakıt sapma %45"));

    fireEvent.click(screen.getByRole("button", { name: /Bakım/i }));
    // Anomali kartı artık görünmüyor (tab filter)
    expect(screen.queryByText("Yakıt sapma %45")).not.toBeInTheDocument();
    expect(screen.getByText("PERIYODIK bakım 3 gün kaldı")).toBeInTheDocument();
  });

  it("critical section başlığı + sayı", async () => {
    (todayService.getTriage as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleResponse,
    );

    render(<TodayPage />);
    await waitFor(() => screen.getByText("Yakıt sapma %45"));
    // "Acil Eylem (1)" başlığı görünür
    expect(screen.getByText(/Acil Eylem \(1\)/i)).toBeInTheDocument();
    // "Bekleyen Aksiyon (2)" başlığı görünür
    expect(screen.getByText(/Bekleyen Aksiyon \(2\)/i)).toBeInTheDocument();
  });

  it('boş data → "Bugün için acil eylem yok" mesajı', async () => {
    (todayService.getTriage as ReturnType<typeof vi.fn>).mockResolvedValue({
      critical_count: 0,
      pending_count: 0,
      items: [],
      active_trips_count: 0,
      completed_today_count: 0,
      computed_at: new Date().toISOString(),
    });
    render(<TodayPage />);
    await waitFor(() =>
      expect(
        screen.getByText(/Bugün için acil eylem yok/i),
      ).toBeInTheDocument(),
    );
  });

  it("Quick Actions bar görünür", async () => {
    (todayService.getTriage as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleResponse,
    );
    render(<TodayPage />);
    await waitFor(() => screen.getByText("Yakıt sapma %45"));
    expect(screen.getByText("Hızlı Erişim")).toBeInTheDocument();
    expect(screen.getByText("Sefer Planla")).toBeInTheDocument();
  });

  it('503 hata → "yüklenemedi" mesajı', async () => {
    (todayService.getTriage as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { status: 503 },
    });
    render(<TodayPage />);
    await waitFor(() =>
      expect(screen.getByText(/yüklenemedi/i)).toBeInTheDocument(),
    );
  });
});
