import type { Metadata } from "next";
import "./globals.css";
import { AppStateProvider } from "@/lib/app-state";

export const metadata: Metadata = {
  title: "SagarNetra · Marine Debris Detection System (NIOT / MoES)",
  description:
    "Scientific hydrographic application for AI-powered physics-verified detection of marine debris in side-scan sonar imagery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased text-text bg-bg select-none">
        <AppStateProvider>{children}</AppStateProvider>
      </body>
    </html>
  );
}
