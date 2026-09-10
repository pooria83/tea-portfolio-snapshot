import type { ReactNode } from "react";
import { WebsiteNavbar } from "@/components/website/WebsiteNavbar";

export default function WebsiteLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-background flex min-h-screen flex-col">
      <WebsiteNavbar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">{children}</main>
      <footer className="relative z-10 border-t py-6">
        <div className="text-muted-foreground mx-auto w-full max-w-6xl px-4 text-center text-sm">
          © {new Date().getFullYear()} AskTea.ai
        </div>
      </footer>
    </div>
  );
}
