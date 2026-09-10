import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Card, Loading } from "../components/ui";
import { DataLabel } from "../components/domain";
import { api, ApiError } from "../api";
import { formatMoney, humanize } from "../lib/format";
import "./AssistantPage.css";

/**
 * AI Assistant: a guided, template-driven helper that answers a small set of
 * common questions by CALLING THE EXISTING BACKEND ENGINES and summarising the
 * result. It introduces NO new backend and does NOT use an LLM — it composes the
 * deterministic decision endpoints, so every answer is explainable and grounded
 * in real backend output. (A conversational LLM layer can be added later.)
 */
type Intent = "fix_or_wait" | "market_read" | "cheapest_origin";

const INTENTS: Array<{ id: Intent; prompt: string }> = [
  { id: "market_read", prompt: "What is the current freight market pressure?" },
  { id: "fix_or_wait", prompt: "Should I fix now or wait on the Australia → Paradip lane?" },
  { id: "cheapest_origin", prompt: "Which origin is cheapest to Paradip right now?" },
];

export default function AssistantPage() {
  const [answer, setAnswer] = useState<{ title: string; body: React.ReactNode } | null>(null);
  const [loading, setLoading] = useState(false);

  const ask = async (intent: Intent) => {
    setLoading(true);
    setAnswer(null);
    try {
      if (intent === "market_read") {
        const r = await api.analytics.marketPressure({
          vessel_supply: 0.35, cargo_demand: 0.75, port_congestion: 60, freight_volatility: 0.5,
        });
        setAnswer({
          title: "Market read",
          body: (
            <p>
              The Freight Market Pressure Index is <strong>{r.index.toFixed(0)}/100</strong>,
              classified <strong>{humanize(r.classification)}</strong>. The largest
              drivers are{" "}
              {r.factors
                .filter((f) => f.available)
                .sort((a, b) => b.contribution - a.contribution)
                .slice(0, 3)
                .map((f) => humanize(f.factor))
                .join(", ")}.
            </p>
          ),
        });
      } else if (intent === "fix_or_wait") {
        const r = await api.analytics.fixWait({
          current_rate: "22", forecast_7d: "21.5", forecast_14d: "21",
          confidence_7d: 0.75, confidence_14d: 0.7, days_to_deadline: 30,
        });
        setAnswer({
          title: "Fix / Wait",
          body: (
            <p>
              Recommended action: <strong>{humanize(r.decision)}</strong>.{" "}
              {r.reason}
            </p>
          ),
        });
      } else {
        const cmp = await api.analytics.compareOrigins([
          { origin: "Australia", destination: "Paradip", cargo_tonnes: "50000", commodity_cost: { amount: "5000000" }, freight_cost: { amount: "1200000" } },
          { origin: "Indonesia", destination: "Paradip", cargo_tonnes: "50000", commodity_cost: { amount: "4800000" }, freight_cost: { amount: "900000" } },
        ]);
        const cheapest = cmp.entries[0];
        setAnswer({
          title: "Cheapest origin",
          body: (
            <p>
              The lowest landed cost to Paradip is from <strong>{cheapest?.origin}</strong>{" "}
              at {cheapest ? formatMoney(cheapest.total_landed_cost) : "—"} total.
            </p>
          ),
        });
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.displayMessage : "The assistant could not complete that request.";
      setAnswer({ title: "Unavailable", body: <p>{message}</p> });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="AI Assistant"
        description="Ask a common question and the assistant answers using the platform's decision engines. Answers are grounded in real backend output — not generated prose."
      />

      <Card title="Ask">
        <div className="assistant-prompts">
          {INTENTS.map((i) => (
            <button key={i.id} className="assistant-prompt" onClick={() => ask(i.id)} disabled={loading}>
              {i.prompt}
            </button>
          ))}
        </div>
      </Card>

      <Card title="Answer">
        {loading ? (
          <Loading fill label="Consulting the engines…" />
        ) : answer ? (
          <div className="assistant-answer">
            <div className="assistant-answer__head">
              <h3>{answer.title}</h3>
              <DataLabel kind="ESTIMATED" />
            </div>
            {answer.body}
          </div>
        ) : (
          <p className="assistant-empty">Pick a question above to get a grounded answer.</p>
        )}
      </Card>
    </>
  );
}
