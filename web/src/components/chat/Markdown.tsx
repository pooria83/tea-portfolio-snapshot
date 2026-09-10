import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { safeHref } from "@/lib/url";

const remarkPlugins = [remarkGfm];

const components: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 ps-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 ps-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  a: ({ children, href }) => {
    const safe = safeHref(href);
    if (!safe) {
      return <span className="underline">{children}</span>;
    }
    return (
      <a href={safe} target="_blank" rel="noreferrer" className="underline">
        {children}
      </a>
    );
  },
  code: ({ children }) => <code className="bg-muted rounded px-1 py-0.5 text-xs">{children}</code>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto last:mb-0">
      <table className="border-border w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-muted/50">{children}</thead>,
  th: ({ children }) => (
    <th className="border-border border-b px-2 py-1.5 text-start font-medium">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border-border border-b px-2 py-1.5 align-top">{children}</td>
  ),
  h1: ({ children }) => <h1 className="mb-2 text-lg font-semibold last:mb-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 text-base font-semibold last:mb-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-2 text-sm font-semibold last:mb-0">{children}</h3>,
  hr: () => <hr className="border-border my-2" />,
};

export function Markdown({ children, dir }: { children: string; dir?: "rtl" | "ltr" | "auto" }) {
  return (
    <div dir={dir}>
      <ReactMarkdown remarkPlugins={remarkPlugins} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
