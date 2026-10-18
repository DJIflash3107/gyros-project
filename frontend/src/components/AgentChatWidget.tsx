import { useEffect, useRef, useState } from "react";
import {
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { useBusiness } from "../context/BusinessContext";
import MarkdownText from "./MarkdownText";
import {
  streamChat,
  type AgentCompleteData,
  type AgentErrorData,
  type AgentMessageDeltaData,
  type AgentStatusData,
} from "../services/agent";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function AgentChatWidget() {
  const { activeBusiness } = useBusiness();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const conversationIdRef = useRef<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.();
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, statusLine]);

  const appendToLastAssistant = (delta: string) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last?.role === "assistant") {
        next[next.length - 1] = { ...last, content: last.content + delta };
      }
      return next;
    });
  };

  const handleSend = () => {
    const text = input.trim();
    if (!text || !activeBusiness || streaming) return;

    setInput("");
    setStreaming(true);
    setStatusLine("Connecting…");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "" },
    ]);

    abortRef.current = streamChat(
      activeBusiness.id,
      {
        message: text,
        ...(conversationIdRef.current
          ? { conversation_id: conversationIdRef.current }
          : {}),
      },
      {
        onEvent: (event) => {
          if (event.conversation_id) {
            conversationIdRef.current = event.conversation_id;
          }
          switch (event.event) {
            case "agent_status": {
              const data = event.data as unknown as AgentStatusData;
              setStatusLine(data.message);
              break;
            }
            case "message_delta": {
              const data = event.data as unknown as AgentMessageDeltaData;
              setStatusLine(null);
              appendToLastAssistant(data.content);
              break;
            }
            case "agent_error": {
              const data = event.data as unknown as AgentErrorData;
              setStatusLine(null);
              appendToLastAssistant(`\n\nError: ${data.message}`);
              break;
            }
            case "agent_complete": {
              const data = event.data as unknown as AgentCompleteData;
              setStatusLine(
                data.tools_used.length > 0
                  ? `Used tools: ${data.tools_used.join(", ")}`
                  : null,
              );
              break;
            }
            default:
              break;
          }
        },
        onError: (error) => {
          setStatusLine(null);
          appendToLastAssistant(`\n\nError: ${error.message}`);
          setStreaming(false);
        },
        onComplete: () => {
          setStatusLine(null);
          setStreaming(false);
        },
      },
    );
  };

  const handleStop = () => {
    abortRef.current?.();
    abortRef.current = null;
    setStatusLine(null);
    setStreaming(false);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-blue-700 text-white shadow-lg transition-colors hover:bg-blue-800"
        aria-label={isOpen ? "Close assistant" : "Open assistant"}
      >
        {isOpen ? (
          <XMarkIcon className="h-6 w-6" />
        ) : (
          <ChatBubbleLeftRightIcon className="h-6 w-6" />
        )}
      </button>

      {isOpen && (
        <div className="fixed bottom-20 right-6 z-40 flex h-[32rem] w-96 max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-200 bg-blue-950 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-white">AI Assistant</p>
              <p className="text-xs text-blue-300">
                {activeBusiness?.name ?? "No business selected"}
              </p>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
            {messages.length === 0 ? (
              <p className="text-sm text-slate-500">
                Ask about sales, inventory, forecasts, or recommendations.
              </p>
            ) : (
              <ul className="space-y-3">
                {messages.map((message, index) => (
                  <li
                    key={index}
                    className={`flex ${
                      message.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                        message.role === "user"
                          ? "whitespace-pre-wrap bg-blue-700 text-white"
                          : "bg-slate-100 text-slate-800"
                      }`}
                    >
                      {message.role === "assistant" ? (
                        message.content ? (
                          <MarkdownText content={message.content} />
                        ) : streaming ? (
                          "…"
                        ) : (
                          ""
                        )
                      ) : (
                        message.content
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {statusLine && (
              <p className="mt-2 text-xs italic text-slate-500">{statusLine}</p>
            )}
          </div>

          <div className="border-t border-slate-200 p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={2}
                placeholder="Type a message…"
                className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
              {streaming ? (
                <button
                  type="button"
                  onClick={handleStop}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Stop
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!input.trim() || !activeBusiness}
                  className="rounded-lg bg-blue-700 p-2 text-white transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="Send message"
                >
                  <PaperAirplaneIcon className="h-5 w-5" />
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
