import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter } from "../../test/utils";
import ChatbotPage from "../ChatbotPage";
import { api } from "../../api";
import type { ChatResponse } from "../../api";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    api: { chat: { send: vi.fn(), reset: vi.fn() } },
  };
});

const sendMock = api.chat.send as unknown as ReturnType<typeof vi.fn>;

const response = (over: Partial<ChatResponse> = {}): ChatResponse => ({
  conversation_id: "c1",
  answer: "For Australia → Paradip: recommended action is MONITOR.",
  sources: ["freight_forecast", "risk"],
  data_used: ["timing_decision", "risk"],
  confidence: 0.73,
  ...over,
});

describe("ChatbotPage", () => {
  beforeEach(() => sendMock.mockReset());

  it("sends a message and renders the grounded answer", async () => {
    sendMock.mockResolvedValue(response());
    renderWithRouter(<ChatbotPage />);
    await userEvent.type(screen.getByLabelText(/Chat message/i), "Should I fix?");
    await userEvent.click(screen.getByRole("button", { name: /^Send$/i }));
    await waitFor(() => expect(sendMock).toHaveBeenCalled());
    expect(await screen.findByText(/recommended action is MONITOR/i)).toBeInTheDocument();
    // Grounding disclosure is shown.
    expect(screen.getByText(/Grounded in:/i)).toBeInTheDocument();
  });

  it("sends a quick question with a fuller grounded prompt", async () => {
    sendMock.mockResolvedValue(response());
    renderWithRouter(<ChatbotPage />);
    await userEvent.click(screen.getByRole("button", { name: /Should I fix now\?/i }));
    await waitFor(() => expect(sendMock).toHaveBeenCalled());
    const arg = sendMock.mock.calls[0][0];
    expect(arg.message).toMatch(/Australia to Paradip/i);
    // Page context is passed to the backend.
    expect(arg.context).toBeTruthy();
  });

  it("resets the conversation and clears the transcript", async () => {
    sendMock.mockResolvedValue(response());
    renderWithRouter(<ChatbotPage />);
    await userEvent.type(screen.getByLabelText(/Chat message/i), "Should I fix?");
    await userEvent.click(screen.getByRole("button", { name: /^Send$/i }));
    expect(await screen.findByText(/recommended action is MONITOR/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Reset conversation/i }));
    // The assistant answer is gone; the greeting remains.
    await waitFor(() =>
      expect(screen.queryByText(/recommended action is MONITOR/i)).not.toBeInTheDocument(),
    );
  });
});
