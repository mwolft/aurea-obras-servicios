import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/auth-provider";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

import "./globals.css";

export const metadata: Metadata = {
  title: "AUREA Obras y Servicios S.L.",
  description: "AUREA Obras y Servicios S.L.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es">
      <body>
        <AuthProvider>
          <div className="appShell">
            <SiteHeader />
            {children}
            <SiteFooter />
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
