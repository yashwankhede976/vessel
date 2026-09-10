/**
 * AI chatbot API. The OpenAI key lives ONLY on the Django backend — this client
 * just posts the user message (+ optional page context) and renders the
 * grounded answer. No secret ever reaches the browser.
 */
import { post, del } from "../client";
import type { ChatContext, ChatResponse } from "../resources";

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  context?: ChatContext;
}

export const chatApi = {
  send(req: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
    return post<ChatResponse>("chat/", req, { signal });
  },
  reset(conversationId: string): Promise<{ conversation_id: string; reset: boolean }> {
    return del<{ conversation_id: string; reset: boolean }>(
      `chat/?conversation_id=${encodeURIComponent(conversationId)}`,
    );
  },
};
