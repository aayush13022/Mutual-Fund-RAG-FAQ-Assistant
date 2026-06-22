export interface ChatResponse {
  answer: string;
  source_url: string | null;
  last_updated_from_sources: string | null;
  disclaimer: string;
  refused: boolean;
  educational_link?: string | null;
}

// Production: always use same-origin /api proxy (server-side → Railway).
// Avoids cross-origin CORS issues and Safari "Load failed" on direct Railway calls.
// Local dev only: set NEXT_PUBLIC_API_URL=http://localhost:8000 to skip the proxy.
const API_BASE = (
  process.env.NODE_ENV === "development" &&
  process.env.NEXT_PUBLIC_API_URL?.trim()
    ? process.env.NEXT_PUBLIC_API_URL.trim()
    : "/api"
).replace(/\/$/, "");

const CHAT_TIMEOUT_MS = 120_000;

function formatFetchError(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "The request timed out. The backend may still be loading models — wait a moment and try again.";
  }
  if (error instanceof TypeError) {
    const text = error.message.toLowerCase();
    if (text.includes("load failed") || text.includes("failed to fetch")) {
      return "Cannot reach the assistant API. On Vercel, set API_URL to your Railway URL and redeploy.";
    }
    return "Cannot reach the assistant API. Check API_URL on Vercel and that Railway is running.";
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export async function postChat(message: string): Promise<ChatResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    });
  } catch (error) {
    throw new Error(formatFetchError(error));
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    const raw = await response.text();
    let detail = raw || `Request failed with status ${response.status}`;
    try {
      const payload = JSON.parse(raw) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Keep raw response text when the body is not JSON.
    }
    throw new Error(detail);
  }

  return response.json();
}
