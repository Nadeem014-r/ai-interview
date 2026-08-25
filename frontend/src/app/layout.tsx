import "./globals.css";
import React from "react";

export const metadata = {
  title: "AI Interviewer Platform — University Placement System",
  description: "Production-grade, adaptive AI interview preparation and candidate evaluation system.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
