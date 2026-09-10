import type { ReactNode } from "react";

import { Bubble, BubbleContent } from "@/components/ui/bubble";
import { intentTheme, type IntentTheme } from "@/lib/chatIntent";
import { cn } from "@/lib/utils";

function IntentIcon({ theme }: { theme: IntentTheme }) {
  if (!theme.Icon) {
    return null;
  }
  const { Icon } = theme;
  return <Icon aria-hidden className="text-muted-foreground mt-1 shrink-0 self-start" size={14} />;
}

export function AssistantBubble({
  intent,
  children,
  className,
}: {
  intent: "greeting" | "search" | "general" | "error" | null | undefined;
  children: ReactNode;
  className?: string;
}) {
  const theme = intentTheme(intent);
  return (
    <Bubble variant={theme.variant}>
      <BubbleContent className={cn("flex gap-2", className)}>
        <IntentIcon theme={theme} />
        <span className="min-w-0 flex-1">{children}</span>
      </BubbleContent>
    </Bubble>
  );
}
