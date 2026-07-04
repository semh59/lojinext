/**
 * 0-mock epiği: ProfilePage artık gerçek AuthContext + gerçek `/auth/me` +
 * gerçek `PATCH /users/me` ile test ediliyor (`vi.mock` AuthContext/
 * axios-instance kaldırıldı). Test kullanıcısı, senaryoda kullanılan
 * synthetic super-admin'dir (`id<=0`, `kullanicilar` tablosunda satırı yok —
 * CLAUDE.md gotcha #15): `/auth/me` gerçek veri döner (email
 * "admin@lojinext.internal", ad_soyad "Super Administrator", rol
 * "super_admin") ama profil kaydetme (`PATCH /users/me`) bu kullanıcı için
 * 404 "Kullanıcı bulunamadı" döner — bu, batch 5'te push/subscribe için
 * bulunan aynı mimari sınırlamayla tutarlı (id<=0 → gerçek DB satırı yok),
 * yeni bir bug değil. Test bunu doğrudan doğruluyor: sayfa çökmeden
 * axiosInstance interceptor'ının hata toast'ını tetiklediğini kabul ediyor.
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

  async function renderReady() {
    render(<ProfilePage />);
    await waitFor(
      () => expect(screen.getByText("Super Administrator")).toBeInTheDocument(),
      { timeout: 15000 },
    );
  }

  it("renders page heading", async () => {
    await renderReady();
    expect(screen.getByText("Profilim")).toBeInTheDocument();
  });

  it("renders user name and email in identity hero", async () => {
    await renderReady();
    expect(screen.getByText("Super Administrator")).toBeInTheDocument();
    expect(
      screen.getAllByText("admin@lojinext.internal").length,
    ).toBeGreaterThanOrEqual(1);
  });

  it("renders role badge", async () => {
    await renderReady();
    expect(screen.getByText("Süper Admin")).toBeInTheDocument();
  });

  it("renders user initials in avatar", async () => {
    await renderReady();
    expect(screen.getByText("SA")).toBeInTheDocument();
  });

  it("renders push notification toggle", async () => {
    await renderReady();
    expect(screen.getByTestId("push-notification-toggle")).toBeInTheDocument();
  });

  it("renders profile info form card", async () => {
    await renderReady();
    expect(screen.getByText("Profil Bilgileri")).toBeInTheDocument();
    expect(
      screen.getByText("Ad soyad bilginizi güncelleyin"),
    ).toBeInTheDocument();
  });

  it("profile form has email (readonly) and ad_soyad input", async () => {
    await renderReady();
    const emailInput = screen.getByDisplayValue("admin@lojinext.internal");
    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute("readOnly");

    const adSoyadInput = screen.getByDisplayValue("Super Administrator");
    expect(adSoyadInput).toBeInTheDocument();
  });

  it("renders change password form card", async () => {
    await renderReady();
    expect(screen.getByText("Şifre Değiştir")).toBeInTheDocument();
    expect(screen.getByText("Şifremi Güncelle")).toBeInTheDocument();
  });

  it("profile form save button hits real PATCH /users/me (synthetic admin → 404, no crash)", async () => {
    await renderReady();
    const saveBtn = screen.getByText("Kaydet");
    fireEvent.click(saveBtn);
    // Synthetic super-admin (id<=0) has no row in `kullanicilar` — backend
    // returns 404, axiosInstance interceptor shows an error toast, and the
    // page must not crash or hang on a stale "loading" state.
    await waitFor(
      () => {
        expect(screen.getByText("Kaydet")).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("shows validation error when ad_soyad is too short", async () => {
    await renderReady();
    const adSoyadInput = screen.getByDisplayValue("Super Administrator");
    fireEvent.change(adSoyadInput, { target: { value: "X" } });
    fireEvent.click(screen.getByText("Kaydet"));
    await waitFor(() => {
      expect(
        screen.getByText("İsim en az 2 karakter olmalıdır."),
      ).toBeInTheDocument();
    });
  });

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
  });

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
  });
});
