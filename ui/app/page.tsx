import type { Metadata } from "next";

import ChatPage from "@/components/chat-page";

export const metadata: Metadata = {
  title: "Mutual Fund FAQ Assistant",
  description: "Facts-only Q&A for 5 HDFC mutual fund schemes.",
};

export default function Page() {
  return <ChatPage />;
}
