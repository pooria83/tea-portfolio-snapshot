import { Hand, Search, Sparkles, TriangleAlert, type LucideIcon } from "lucide-react";

import type { ChatIntent } from "@/types/chat-history";

export interface IntentTheme {
  variant: "muted" | "secondary" | "tinted" | "destructive";
  Icon: LucideIcon | null;
}

const INTENT_THEMES: Record<ChatIntent, IntentTheme> = {
  greeting: { variant: "tinted", Icon: Hand },
  search: { variant: "secondary", Icon: Search },
  general: { variant: "muted", Icon: Sparkles },
  error: { variant: "destructive", Icon: TriangleAlert },
};

export function intentTheme(intent: ChatIntent | null | undefined): IntentTheme {
  return intent ? INTENT_THEMES[intent] : { variant: "muted", Icon: null };
}
