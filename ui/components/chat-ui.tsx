import type { ReactNode } from "react";

import { DISCLAIMER, EXAMPLE_QUESTIONS, SUPPORTED_SCHEMES, WELCOME_MESSAGE } from "@/lib/constants";

export function MaterialIcon({
  name,
  filled = false,
  className = "",
}: {
  name: string;
  filled?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={filled ? { fontVariationSettings: "'FILL' 1" } : undefined}
      aria-hidden
    >
      {name}
    </span>
  );
}

export function DisclaimerBanner() {
  return (
    <div className="fixed left-0 right-0 top-0 z-[60] flex items-start gap-2 border-b border-tertiary/20 bg-tertiary-container/30 px-4 py-2 backdrop-blur-sm md:items-center md:justify-center md:px-6">
      <MaterialIcon name="warning" filled className="mt-0.5 text-[16px] text-tertiary md:mt-0 md:text-[18px]" />
      <div className="flex-1 md:flex-none">
        <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider text-tertiary md:hidden">
          Disclaimer
        </p>
        <p className="text-sm font-semibold text-tertiary md:text-base">{DISCLAIMER}</p>
      </div>
    </div>
  );
}

export function ChatHeader() {
  return (
    <header className="fixed left-0 right-0 top-[52px] z-50 border-b border-outline-variant/50 bg-surface-container-low md:top-[40px]">
      <div className="mx-auto flex max-w-chat items-center justify-between px-4 py-3 md:px-6 md:py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-container text-on-primary-container">
            <MaterialIcon name="forum" />
          </div>
          <h1 className="text-lg font-semibold text-primary md:text-2xl">Mutual Fund FAQ Assistant</h1>
        </div>
        <div className="hidden items-center gap-2 md:flex">
          <MaterialIcon name="verified" className="text-primary" />
          <span className="text-sm text-on-surface-variant">HDFC · 5 schemes</span>
        </div>
      </div>
    </header>
  );
}

export function WelcomeBlock() {
  return (
    <div className="max-w-[90%] self-start rounded-xl rounded-tl-sm border border-outline-variant/50 bg-surface-container-lowest shadow-sm md:max-w-[85%]">
      <div className="flex flex-col gap-3 px-bubble-x py-bubble-y">
        <p className="text-base text-on-surface">{WELCOME_MESSAGE}</p>
        <div>
          <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-on-surface-variant">
            Supported schemes
          </p>
          <ul className="space-y-1.5">
            {SUPPORTED_SCHEMES.map((scheme) => (
              <li key={scheme} className="flex items-start gap-2 text-sm text-on-surface">
                <MaterialIcon name="check_circle" className="mt-0.5 shrink-0 text-[16px] text-primary" />
                <span>{scheme}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export function ExampleChips({
  disabled,
  onSelect,
}: {
  disabled: boolean;
  onSelect: (question: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2 self-start pl-0 md:pl-2">
      {EXAMPLE_QUESTIONS.map((question) => (
        <button
          key={question}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(question)}
          className="max-w-full truncate rounded-full border border-outline-variant/60 bg-surface-container-low px-3 py-1.5 text-left text-sm text-primary transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-50 md:px-4 md:py-2"
        >
          {question}
        </button>
      ))}
    </div>
  );
}

export type ChatMessageItem =
  | { id: string; role: "user"; text: string; timestamp: string }
  | {
      id: string;
      role: "bot";
      text: string;
      timestamp: string;
      refused: boolean;
      sourceUrl?: string | null;
      lastUpdated?: string | null;
      educationalLink?: string | null;
      loading?: boolean;
      error?: boolean;
    };

export function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function UserBubble({ text, timestamp }: { text: string; timestamp: string }) {
  return (
    <div className="flex w-full flex-col items-end gap-1 self-end">
      <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary-container px-bubble-x py-bubble-y text-on-primary-container shadow-sm md:max-w-[80%]">
        <p className="text-base">{text}</p>
      </div>
      <span className="pr-1 text-[10px] text-on-surface-variant">{timestamp}</span>
    </div>
  );
}

export function BotBubble({
  message,
  onRetry,
}: {
  message: Extract<ChatMessageItem, { role: "bot" }>;
  onRetry?: () => void;
}) {
  if (message.loading) {
    return (
      <div className="max-w-[90%] self-start rounded-xl rounded-tl-sm border border-outline-variant/50 bg-surface-container-low px-bubble-x py-bubble-y md:max-w-[85%]">
        <div className="flex items-center gap-2 text-on-surface-variant">
          <MaterialIcon name="hourglass_top" className="animate-pulse text-primary" />
          <span className="text-sm">Finding an answer...</span>
        </div>
      </div>
    );
  }

  if (message.error) {
    return (
      <div className="max-w-[90%] self-start rounded-xl rounded-tl-sm border border-error/30 bg-error-container/20 px-bubble-x py-bubble-y md:max-w-[85%]">
        <p className="mb-3 text-base text-on-surface">{message.text}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-lg bg-primary-container px-3 py-1.5 text-sm font-semibold text-on-primary-container hover:opacity-90"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  if (message.refused) {
    return (
      <div className="relative max-w-[90%] self-start overflow-hidden rounded-xl rounded-tl-sm border border-outline-variant/50 bg-surface-container-lowest md:max-w-[85%]">
        <div className="absolute bottom-0 left-0 top-0 w-1 bg-tertiary" />
        <div className="flex flex-col gap-3 px-bubble-x py-bubble-y pl-5">
          <div className="flex items-start gap-2">
            <MaterialIcon name="policy" className="text-[20px] text-tertiary" />
            <p className="text-base text-on-surface">{message.text}</p>
          </div>
          {message.educationalLink && (
            <>
              <div className="h-px w-full bg-surface-container-highest" />
              <a
                href={message.educationalLink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex w-fit items-center gap-1 text-sm text-primary hover:underline"
              >
                <MaterialIcon name="school" className="text-[16px]" />
                Learn about investing responsibly
                <MaterialIcon name="arrow_forward" className="text-[16px]" />
              </a>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[90%] self-start rounded-xl rounded-tl-sm border border-outline-variant/50 bg-surface-container-lowest md:max-w-[85%]">
      <div className="flex flex-col gap-3 px-bubble-x py-bubble-y">
        <div className="flex items-center gap-2">
          <MaterialIcon name="verified" filled className="text-[16px] text-primary" />
          <span className="text-[10px] font-semibold uppercase tracking-wide text-primary">Factual Data</span>
        </div>
        <p className="text-base text-on-surface">{message.text}</p>
        {(message.sourceUrl || message.lastUpdated) && (
          <div className="rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-2">
            {message.sourceUrl && (
              <a
                href={message.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex items-center gap-1 text-sm text-primary hover:underline"
              >
                View source on Groww
                <MaterialIcon name="open_in_new" className="text-[16px] transition-transform group-hover:translate-x-0.5" />
              </a>
            )}
            {message.lastUpdated && (
              <p className="mt-1 flex items-center gap-1 text-[11px] text-on-surface-variant">
                <MaterialIcon name="update" className="text-[14px]" />
                Last updated from sources: {message.lastUpdated}
              </p>
            )}
          </div>
        )}
        <p className="text-[11px] text-outline">{DISCLAIMER}</p>
      </div>
    </div>
  );
}

export function ChatInput({
  value,
  disabled,
  onChange,
  onSubmit,
}: {
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-outline-variant/50 bg-surface p-4">
      <div className="relative mx-auto max-w-chat">
        <input
          type="text"
          value={value}
          disabled={disabled}
          placeholder="Ask a factual question about a scheme..."
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
          className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest py-3 pl-4 pr-14 text-base text-on-surface placeholder:text-outline outline-none transition-shadow focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-60"
        />
        <button
          type="button"
          disabled={disabled || !value.trim()}
          onClick={onSubmit}
          aria-label="Send message"
          className="absolute right-2 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-lg text-primary transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
        >
          <MaterialIcon name="send" filled />
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-chat text-center text-xs text-outline">
        Responses are generated automatically based on factual scheme documents.
      </p>
    </div>
  );
}
