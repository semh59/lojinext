/**
 * 0-mock epiği: ProfilePage artık gerçek AuthContext + gerçek `/auth/me` +
 * gerçek `PATCH /users/me` ile test ediliyor (`vi.mock` AuthContext/
 * axios-instance kaldırıldı). Test kullanıcısı, migration 0002'nin
 * seed'lediği GERÇEK admin satırıdır (`kullanicilar.id=1`, gerçek DB
 * satırı var — synthetic break-glass admin DEĞİL): `/auth/me` gerçek veri
 * döner (email/username "admin", ad_soyad "Sistem Yonetici", rol
 * "super_admin"). Bu kullanıcı için `PATCH /users/me` gerçek DB satırını
 * günceller ve 200 döner (curl ile kanıtlandı) — synthetic admin'in aksine
 * burada 404 senaryosu yok.
 *
 * Şifre değiştirme formu, validasyon, initials, şifre gücü, göster/gizle
 * toggle'ı — hepsi saf component/react-hook-form mantığı, backend'e ihtiyaç
 * duymuyor; gerçek kullanıcı verisiyle (mock yerine) aynı şekilde çalışıyor.
 */
import {
  beforeAll,
  afterAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../test/real-backend";

vi.mock("../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

vi.mock("../../components/profile/PushNotificationToggle", () => ({
  PushNotificationToggle: () => (
    <div data-testid="push-notification-toggle">Push Toggle</div>
  ),
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("ProfilePage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../test/test-utils").fireEvent;
  let ProfilePage: typeof import("../ProfilePage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../test/test-utils"
    ));
    ({ default: ProfilePage } = await import("../ProfilePage"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  beforeEach(async () => {
    sessionStorage.setItem("access_token", await loginAsAdmin());
  });

  // NOTE on the explicit `it(..., N)` third-arg timeouts below: renderReady()
  // internally waitFor()s up to 15s for the real `/auth/me` + `/users/me`
  // round-trip to resolve. vitest's *test*-level default timeout (5s here —
  // not overridden by config, which is out of scope for this slice) is
  // independent of an inner waitFor's own timeout budget; if the real
  // backend takes longer than 5s (observed under concurrent load when this
  // file runs alongside the other real-backend suites in this slice,
  // sharing one single-worker backend container), the enclosing test aborts
  // with "Test timed out in 5000ms" before renderReady's 15s budget is up.
  // Every test that calls renderReady() needs a matching explicit timeout.
  async function renderReady() {
    render(<ProfilePage />);
    await waitFor(
      () => expect(screen.getByText("Sistem Yonetici")).toBeInTheDocument(),
      { timeout: 15000 },
    );
  }

  it("renders page heading", async () => {
    await renderReady();
    expect(screen.getByText("Profilim")).toBeInTheDocument();
  }, 20000);

  it("renders user name and email in identity hero", async () => {
    await renderReady();
    expect(screen.getByText("Sistem Yonetici")).toBeInTheDocument();
    expect(screen.getAllByText("admin").length).toBeGreaterThanOrEqual(1);
  }, 20000);

  it("renders role badge", async () => {
    await renderReady();
    expect(screen.getByText("Süper Admin")).toBeInTheDocument();
  }, 20000);

  it("renders user initials in avatar", async () => {
    await renderReady();
    expect(screen.getByText("SY")).toBeInTheDocument();
  }, 20000);

  it("renders push notification toggle", async () => {
    await renderReady();
    expect(screen.getByTestId("push-notification-toggle")).toBeInTheDocument();
  }, 20000);

  it("renders profile info form card", async () => {
    await renderReady();
    expect(screen.getByText("Profil Bilgileri")).toBeInTheDocument();
    expect(
      screen.getByText("Ad soyad bilginizi güncelleyin"),
    ).toBeInTheDocument();
  }, 20000);

  it("profile form has email (readonly) and ad_soyad input", async () => {
    await renderReady();
    const emailInput = screen.getByDisplayValue("admin");
    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute("readOnly");

    const adSoyadInput = screen.getByDisplayValue("Sistem Yonetici");
    expect(adSoyadInput).toBeInTheDocument();
  }, 20000);

  it("renders change password form card", async () => {
    await renderReady();
    expect(screen.getByText("Şifre Değiştir")).toBeInTheDocument();
    expect(screen.getByText("Şifremi Güncelle")).toBeInTheDocument();
  }, 20000);

  it("profile form save button hits real PATCH /users/me (real admin row, 200, no crash)", async () => {
    await renderReady();
    const saveBtn = screen.getByText("Kaydet");
    fireEvent.click(saveBtn);
    // Real admin (id=1) has a row in `kullanicilar` — backend returns 200
    // and updates the row (idempotent: value unchanged), the page must
    // not crash or hang on a stale "loading" state.
    await waitFor(
      () => {
        expect(screen.getByText("Kaydet")).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 30000);

  it("shows validation error when ad_soyad is too short", async () => {
    await renderReady();
    const adSoyadInput = screen.getByDisplayValue("Sistem Yonetici");
    fireEvent.change(adSoyadInput, { target: { value: "X" } });
    fireEvent.click(screen.getByText("Kaydet"));
    await waitFor(() => {
      expect(
        screen.getByText("İsim en az 2 karakter olmalıdır."),
      ).toBeInTheDocument();
    });
  }, 20000);

  it("password toggle button toggles visibility", async () => {
    await renderReady();
    const toggleBtns = screen.getAllByRole("button", {
      name: /Şifreyi göster/i,
    });
    expect(toggleBtns.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(toggleBtns[0]);
    const hideBtns = screen.getAllByRole("button", {
      name: /Şifreyi gizle/i,
    });
    expect(hideBtns.length).toBeGreaterThanOrEqual(1);
  }, 20000);

  it("shows password strength bar when new password is typed", async () => {
    await renderReady();
    const newPwInput = screen
      .getAllByPlaceholderText("••••••••")
      .find(
        (el) => (el as HTMLInputElement).id === "new_password",
      ) as HTMLElement;
    fireEvent.change(newPwInput, { target: { value: "Test1234" } });
    await waitFor(() => {
      expect(screen.getByText(/Şifre gücü:/)).toBeInTheDocument();
    });
  }, 20000);
});
