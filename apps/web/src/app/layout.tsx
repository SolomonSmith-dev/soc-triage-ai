import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SOC Triage Copilot",
  description: "Tier-1 alert triage, MITRE ATT&CK grounded.",
};

// TODO(P2): wrap children with NextAuth SessionProvider
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>
        <div className="min-h-screen">
          <header className="border-b border-border">
            <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
              <div>
                <h1 className="text-lg font-bold">SOC Triage Copilot</h1>
                <p className="text-xs text-ink-mute">
                  Tier-1 alert triage · MITRE ATT&amp;CK grounded
                </p>
              </div>
              <nav className="flex gap-4 text-sm">
                <a href="/" className="hover:text-ink">Dashboard</a>
                <a href="/submit" className="hover:text-ink">Submit alert</a>
                <a href="/eval" className="hover:text-ink">Evaluation</a>
              </nav>
            </div>
          </header>
          <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
