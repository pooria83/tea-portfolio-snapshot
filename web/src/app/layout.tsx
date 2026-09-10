import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
};

const themeInitScript = `(function(){try{var t=localStorage.getItem("theme");if(t==="dark"||t==="light"){document.documentElement.classList.remove("dark","light");document.documentElement.classList.add(t);}}catch(e){}})();`;

export default function RootLayout({ children }: Props) {
  return (
    <html className="dark h-full" suppressHydrationWarning lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="flex min-h-full flex-col antialiased">{children}</body>
    </html>
  );
}
