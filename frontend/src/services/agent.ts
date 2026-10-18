import { getToken } from "./apiClient";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export interface AgentChatRequest {
  message: string;
  conversation_id?: string;
  context?: Record<string, unknown>;
}

export type AgentEventType =
  | "agent_status"
  | "tool_start"
  | "tool_result"
  | "message_delta"
  | "approval_required"
  | "agent_error"
  | "agent_complete";

export interface AgentSSEEvent {
  event: AgentEventType;
  data: Record<string, unknown>;
  timestamp: number;
  conversation_id: string | null;
}

export interface AgentStatusData {
  status: string;
  message: string;
}

export interface AgentMessageDeltaData {
  content: string;
  finish_reason: string | null;
}

export interface AgentToolStartData {
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface AgentToolResultData {
  tool_name: string;
  summary: string;
  data: Record<string, unknown> | null;
}

export interface AgentCompleteData {
  total_tokens: number | null;
  tools_used: string[];
  duration_ms: number;
}

export interface AgentErrorData {
  error_code: string;
  message: string;
}

export interface AgentStreamCallbacks {
  onEvent?: (event: AgentSSEEvent) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export function streamChat(
  businessId: number,
  chatRequest: AgentChatRequest,
  callbacks: AgentStreamCallbacks,
): () => void {
  const controller = new AbortController();

  void (async () => {
    try {
      const token = getToken();
      const response = await fetch(
        `${BASE_URL}/agent/businesses/${businessId}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(chatRequest),
          signal: controller.signal,
        },
      );

      if (!response.ok || !response.body) {
        let message = "Agent request failed";
        try {
          const envelope = await response.json();
          message =
            envelope.message?.error ??
            Object.values(envelope.error ?? {})[0] ??
            message;
        } catch {
          // keep default message
        }
        throw new Error(message);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          const payload = frame
            .split("\n")
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.slice(5).trimStart())
            .join("\n")
            .trim();
          if (!payload) continue;
          if (payload === "[DONE]") {
            callbacks.onComplete?.();
            return;
          }
          try {
            callbacks.onEvent?.(JSON.parse(payload) as AgentSSEEvent);
          } catch {
            // ignore malformed frames
          }
        }
      }
      callbacks.onComplete?.();
    } catch (err) {
      if (controller.signal.aborted) return;
      callbacks.onError?.(
        err instanceof Error ? err : new Error("Agent stream failed"),
      );
    }
  })();

  return () => controller.abort();
}
