import { Link } from "@/i18n/routing";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-4xl font-bold">404</h1>
      <p className="text-muted-foreground text-sm">Page not found</p>
      <Link
        href="/"
        className="text-primary hover:text-primary/80 text-sm underline transition-colors"
      >
        Go home
      </Link>
    </main>
  );
}
