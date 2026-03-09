import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MigrateIQ — AI-powered BI Migration Validation",
  description: "Automated Tableau to Power BI migration validation platform",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
