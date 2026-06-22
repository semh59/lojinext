import { describe, expect, it, vi, beforeEach } from "vitest";

const sendFeedback = vi.hoisted(() => vi.fn());
vi.mock("@/api/feedback", () => ({ sendFeedback }));

import { render, screen, fireEvent, waitFor } from "../../../test/test-utils";
import { FeedbackButton } from "../FeedbackButton";

describe("FeedbackButton", () => {
  beforeEach(() => {
    sendFeedback.mockReset();
  });

  it("opens modal, submits feedback with page path, shows thanks", async () => {
    sendFeedback.mockResolvedValueOnce(undefined);
    render(<FeedbackButton />);

    fireEvent.click(screen.getByLabelText("Geri bildirim gönder"));
    const textarea = screen.getByPlaceholderText(/Önerinizi/i);
    fireEvent.change(textarea, { target: { value: "harika bir araç" } });
    fireEvent.click(screen.getByRole("button", { name: "Gönder" }));

    await waitFor(() => expect(sendFeedback).toHaveBeenCalledTimes(1));
    expect(sendFeedback).toHaveBeenCalledWith({
      message: "harika bir araç",
      page: "/",
    });
    await screen.findByText(/Teşekkürler/i);
  });

  it("shows error message when send fails", async () => {
    sendFeedback.mockRejectedValueOnce(new Error("500"));
    render(<FeedbackButton />);
    fireEvent.click(screen.getByLabelText("Geri bildirim gönder"));
    fireEvent.change(screen.getByPlaceholderText(/Önerinizi/i), {
      target: { value: "sorun var" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Gönder" }));
    await screen.findByText(/Gönderilemedi/i);
  });

  it("disables submit when message is empty", () => {
    render(<FeedbackButton />);
    fireEvent.click(screen.getByLabelText("Geri bildirim gönder"));
    expect(screen.getByRole("button", { name: "Gönder" })).toBeDisabled();
  });
});
