import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "AUREA Obras y Servicios S.L.",
  description: "AUREA Obras y Servicios S.L.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
