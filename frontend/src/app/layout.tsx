import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/auth-provider";
import { SiteFooter } from "@/components/site-footer";
import { siteUrl } from "@/lib/site";
import { SiteHeader } from "@/components/site-header";

import "./globals.css";

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "AUREA Obras y Servicios S.L.",
  description: "Obras, jardinería y alquiler de herramientas de AUREA Obras y Servicios S.L.",
};

export const viewport: Viewport = {
  themeColor: "#102A43",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es">
      <body className={ibmPlexSans.className}>
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
