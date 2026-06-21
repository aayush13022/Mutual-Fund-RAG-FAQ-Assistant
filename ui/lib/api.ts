export interface ChatResponse {
  answer: string;
  source_url: string | null;
  last_updated_from_sources: string | null;
  disclaimer: string;
  refused: boolean;
  educational_link?: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function postChat(message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    const raw = await response.text();
    let message = raw || `Request failed with status ${response.status}`;
    try {
      const payload = JSON.parse(raw) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Keep raw response text when the body is not JSON.
    }
    throw new Error(message);
  }

  return response.json();
}
