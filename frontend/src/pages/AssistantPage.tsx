import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import { Card, FormField, Loading } from "../components/ui";
import { DataLabel } from "../components/domain";
import { api, ApiError } from "../api";
import type { AssistantAnswer } from "../api";
import { humanize } from "../lib/format";
import "./AssistantPage.css";

/**
 * AI Assistant. Sends the question to POST /decision/assistant/, which
 * classifies the intent and answers from the real decision engines. It does NOT
 * use an LLM and NEVER invents values — every answer is grounded in backend
 * output (a conversational LLM layer could be added on top later).
 */
const SAMPLE_QUESTIONS = [
  "Should I fix Australia to Paradip?",
  "Which vessel is best?",
  "Is Dhamra better than Paradip?",
  "Spot or multi-voyage?",
  "What happens if freight increases 10%?",
];

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async (q: string) => {
    const text = q.trim();
    if (!text) return;
    setQuestion(text);
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await api.decision.ask(text));
    } catch (err) {
      setError(err instanceof ApiError ? err.displayMessage : "The assistant could not answer that.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="AI Assistant"
        description="Ask a chartering question and the assistant answers from the platform's decision engines. Answers are grounded in real backend output — never generated values."
      />

      <Card title="Ask">
        <form
          className="assistant-ask"
          onSubmit={(e) => { e.preventDefault(); ask(question); }}
        >
          <div className="assistant-ask__field">
            <FormField
              label="Question"
              placeholder="e.g. Should I fix Australia to Paradip?"
              value={question}
              onChange={setQuestion}
            />
          </div>
          <button type="submit" className="btn btn--primary" disabled={loading}>
            {loading ? "Thinking…" : "Ask"}
          </button>
        </form>
        <div className="assistant-prompts">
          {SAMPLE_QUESTIONS.map((q) => (
            <button key={q} className="assistant-prompt" onClick={() => ask(q)} disabled={loading}>
              {q}
            </button>
          ))}
        </div>
      </Card>

      <Card title="Answer">
        {loading ? (
          <Loading fill label="Consulting the engines…" />
        ) : error ? (
          <p className="assistant-error">{error}</p>
        ) : answer ? (
          <div className="assistant-answer">
            <div className="assistant-answer__head">
              <h3>{humanize(answer.intent)}</h3>
              <DataLabel kind="ESTIMATED" />
            </div>
            <p>{answer.answer}</p>
          </div>
        ) : (
          <p className="assistant-empty">Ask a question above to get a grounded answer.</p>
        )}
      </Card>
    </>
  );
}
