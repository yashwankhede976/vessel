import { useEffect, useRef, useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Card } from "../components/ui";
import { DataLabel } from "../components/domain";
import { api, ApiError } from "../api";
import type { ChatContext, ChatResponse } from "../api";
import { humanize } from "../lib/format";
import "./ChatbotPage.css";

/**
 * AI Chatbot — a conversational panel over POST /api/v1/chat/.
 *
 * The OpenAI API key lives ONLY on the Django backend; this page never sees it.
 * The backend grounds every answer in the platform's own decision engines and
 * (when a key is configured) uses OpenAI to phrase it — otherwise it returns a
 * deterministic grounded answer. Either way, nothing is invented client-side.
 */
interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  sources?: string[];
  dataUsed?: string[];
  confidence?: number | null;
  error?: boolean;
}

const QUICK_QUESTIONS = [
  "Should I fix now?",
  "Best vessel?",
  "Best port?",
  "Compare origins",
  "Spot vs contract",
];

// Map the short quick-question labels to fuller prompts for better grounding.
const QUICK_PROMPTS: Record<string, string> = {
  "Should I fix now?": "Should I fix Australia to Paradip now or wait?",
  "Best vessel?": "Which vessel is best for 100,000 MT coal Australia to Paradip?",
  "Best port?": "Compare Paradip and Dhamra for coal from Australia.",
  "Compare origins": "Which is cheaper into Paradip, Australia or Indonesia?",
  "Spot vs contract": "Spot or multi-voyage for Australia to Paradip?",
};

const GREETING: ChatMessage = {
  id: 0,
  role: "assistant",
  text:
    "Hi — I'm your freight procurement and vessel chartering assistant for East " +
    "Coast India bulk cargo. Ask about timing (fix/wait), the best vessel, port " +
    "or origin comparisons, contract choice, or a freight-change what-if. Every " +
    "answer is grounded in the platform's own data — I won't invent rates, " +
    "vessels, costs or forecasts.",
};

/** Optional page context. In a full integration this would be lifted from the
 * active cargo/route/forecast page; here we default to the demo lane so the
 * chatbot is grounded even when opened standalone. */
const DEFAULT_CONTEXT: ChatContext = {
  origin: "Australia",
  destination: "Paradip",
  commodity: "Coal",
  cargo_quantity: "100000",
};

export default function ChatbotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const nextId = useRef(1);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Guard: jsdom (tests) does not implement Element.scrollTo.
    const el = listRef.current;
    if (el && typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages, busy]);

  const send = async (raw: string) => {
    const text = raw.trim();
    if (!text || busy) return;

    setMessages((m) => [...m, { id: nextId.current++, role: "user", text }]);
    setInput("");
    setBusy(true);

    try {
      const res: ChatResponse = await api.chat.send({
        message: text,
        conversation_id: conversationId,
        context: DEFAULT_CONTEXT,
      });
      setConversationId(res.conversation_id);
      setMessages((m) => [
        ...m,
        {
          id: nextId.current++,
          role: "assistant",
          text: res.answer,
          sources: res.sources,
          dataUsed: res.data_used,
          confidence: res.confidence,
        },
      ]);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.displayMessage : "The assistant is unavailable right now.";
      setMessages((m) => [...m, { id: nextId.current++, role: "assistant", text: msg, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    const id = conversationId;
    setMessages([GREETING]);
    setConversationId(undefined);
    setInput("");
    if (id) {
      try { await api.chat.reset(id); } catch { /* best-effort */ }
    }
  };

  return (
    <>
      <PageHeader
        title="AI Chatbot"
        description="Ask freight and chartering questions in natural language. Answers are grounded in the platform's decision engines. The OpenAI key is backend-only and never exposed to the browser."
        actions={
          <button className="btn btn--ghost" onClick={reset} disabled={busy}>
            Reset conversation
          </button>
        }
      />

      <Card>
        <div className="chatbot">
          <div className="chatbot__messages" ref={listRef}>
            {messages.map((m) => (
              <div key={m.id} className={`chatbot__row chatbot__row--${m.role}`}>
                <div className={`chatbot__bubble chatbot__bubble--${m.role}${m.error ? " chatbot__bubble--error" : ""}`}>
                  <p className="chatbot__text">{m.text}</p>
                  {m.role === "assistant" && !m.error && m.dataUsed && m.dataUsed.length > 0 && (
                    <div className="chatbot__meta">
                      <DataLabel kind="ESTIMATED" />
                      <span className="chatbot__sources">
                        Grounded in: {m.dataUsed.slice(0, 6).map(humanize).join(", ")}
                        {m.dataUsed.length > 6 ? "…" : ""}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="chatbot__row chatbot__row--assistant">
                <div className="chatbot__bubble chatbot__bubble--assistant chatbot__bubble--typing">
                  <span className="chatbot__dot" />
                  <span className="chatbot__dot" />
                  <span className="chatbot__dot" />
                </div>
              </div>
            )}
          </div>

          <div className="chatbot__quick">
            {QUICK_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                className="chatbot__chip"
                onClick={() => void send(QUICK_PROMPTS[q] ?? q).catch(() => {})}
                disabled={busy}
              >
                {q}
              </button>
            ))}
          </div>

          <form
            className="chatbot__composer"
            onSubmit={(e) => {
              e.preventDefault();
              // send() handles its own errors; attach a no-op catch so the
              // returned promise is never treated as unhandled.
              void send(input).catch(() => {});
            }}
          >
            <input
              className="chatbot__input"
              type="text"
              placeholder="Ask about fix/wait, vessels, ports, cost, contract…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
              aria-label="Chat message"
            />
            <button type="submit" className="btn btn--primary" disabled={busy || !input.trim()}>
              {busy ? "…" : "Send"}
            </button>
          </form>
        </div>
      </Card>
    </>
  );
}
