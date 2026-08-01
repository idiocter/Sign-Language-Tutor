// Global 404 for requests that don't resolve to a locale. Renders its own document
// because it sits outside the [locale] layout.
import "./globals.css";

export default function GlobalNotFound() {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center gap-4">
          <h1 className="text-5xl font-bold">404</h1>
          <a href="/" className="text-[var(--accent)] hover:underline">
            Home
          </a>
        </div>
      </body>
    </html>
  );
}
