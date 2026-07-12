/**
 * Regression: the duplicate-email backend error ("Bu e-posta adresi zaten
 * kullanımda") used to also flag the Full Name field as errored, because
 * the field's error check was `formError.includes("ad")` — a substring
 * that also matches "adresi" inside the unrelated email error message.
 * Fixed by checking for "soyad" instead, which only appears in this
 * field's own validation message ("Ad Soyad zorunludur").
 */
import { render, screen } from "../../../test/test-utils";
import { describe, it, expect, vi } from "vitest";
import { UserRolePanel } from "../UserRolePanel";

const baseProps = {
  form: {
    email: "admin@lojinext.com",
    ad_soyad: "Test Kullanici",
    sifre: "",
    rol_id: "3",
    aktif: true,
  },
  modalMode: "create" as const,
  roles: [{ id: 3, ad: "admin" }] as any,
  isBusy: false,
  onSubmit: vi.fn(),
  onClose: vi.fn(),
  onFieldChange: (key: string) => ({
    value: (baseProps.form as any)[key],
    onChange: vi.fn(),
  }),
  onRolChange: vi.fn(),
  onAktifToggle: vi.fn(),
};

describe("UserRolePanel", () => {
  it("duplicate-email error only flags the E-Mail field, not Full Name", () => {
    render(
      <UserRolePanel
        {...baseProps}
        formError="Bu e-posta adresi zaten kullanımda"
      />,
    );

    const emailInput = screen.getByPlaceholderText("user@company.com");
    const nameInput = screen.getByPlaceholderText("John Smith");

    expect(emailInput).toHaveAttribute("aria-invalid", "true");
    expect(nameInput).toHaveAttribute("aria-invalid", "false");
  });

  it("'Ad Soyad zorunludur' error flags only the Full Name field", () => {
    render(<UserRolePanel {...baseProps} formError="Ad Soyad zorunludur" />);

    const emailInput = screen.getByPlaceholderText("user@company.com");
    const nameInput = screen.getByPlaceholderText("John Smith");

    expect(nameInput).toHaveAttribute("aria-invalid", "true");
    expect(emailInput).toHaveAttribute("aria-invalid", "false");
  });
});
