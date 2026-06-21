"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  BotBubble,
  ChatHeader,
  ChatInput,
  DisclaimerBanner,
  ExampleChips,
  formatTime,
  type ChatMessageItem,
  UserBubble,
  WelcomeBlock,
} from "@/components/chat-ui";
import { postChat } from "@/lib/api";

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastFailedQuestion, setLastFailedQuestion] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendQuestion = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || loading) {
        return;
      }

      const userTimestamp = formatTime(new Date());
      const loadingId = createId();

      setInput("");
      setLastFailedQuestion(null);
      setMessages((current) => [
        ...current,
        { id: createId(), role: "user", text: trimmed, timestamp: userTimestamp },
        {
          id: loadingId,
          role: "bot",
          text: "",
          timestamp: userTimestamp,
          refused: false,
          loading: true,
        },
      ]);
      setLoading(true);

      try {
        const response = await postChat(trimmed);
        setMessages((current) =>
          current.map((message) =>
            message.id === loadingId
              ? {
                  id: loadingId,
                  role: "bot",
                  text: response.answer,
                  timestamp: formatTime(new Date()),
                  refused: response.refused,
                  sourceUrl: response.source_url,
                  lastUpdated: response.last_updated_from_sources,
                  educationalLink: response.educational_link,
                }
              : message,
          ),
        );
      } catch (error) {
        const errorText =
          error instanceof Error && error.message.trim()
            ? error.message
            : "Something went wrong. Please try again.";
        setLastFailedQuestion(trimmed);
        setMessages((current) =>
          current.map((message) =>
            message.id === loadingId
              ? {
                  id: loadingId,
                  role: "bot",
                  text: errorText,
                  timestamp: formatTime(new Date()),
                  refused: false,
                  error: true,
                }
              : message,
          ),
        );
      } finally {
        setLoading(false);
      }
    },
    [loading],
  );

  return (
    <div className="flex min-h-screen flex-col bg-surface text-on-surface">
      <DisclaimerBanner />
      <ChatHeader />

      <main className="mx-auto mb-[140px] mt-[116px] flex w-full max-w-chat flex-1 flex-col gap-chat-gap overflow-y-auto px-4 pb-6 md:mt-[120px]">
        <WelcomeBlock />
        <ExampleChips disabled={loading} onSelect={sendQuestion} />

        {messages.map((message) =>
          message.role === "user" ? (
            <UserBubble key={message.id} text={message.text} timestamp={message.timestamp} />
          ) : (
            <BotBubble
              key={message.id}
              message={message}
              onRetry={
                message.error && lastFailedQuestion
                  ? () => sendQuestion(lastFailedQuestion)
                  : undefined
              }
            />
          ),
        )}
        <div ref={bottomRef} />
      </main>

      <ChatInput
        value={input}
        disabled={loading}
        onChange={setInput}
        onSubmit={() => sendQuestion(input)}
      />
    </div>
  );
}
