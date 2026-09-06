import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/auth-provider";
import { CookieConsent } from "@/components/cookie-consent";
import { GoogleAnalytics } from "@/components/google-analytics";
import { ScrollToTop } from "@/components/scroll-to-top";
import { SiteFooter } from "@/components/site-footer";
import { legalInfo } from "@/lib/legal";
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
  title: legalInfo.companyName,
  description: `Obras, jardinería y alquiler de herramientas de ${legalInfo.companyName}.`,
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
            <ScrollToTop />
            <CookieConsent />
            <GoogleAnalytics />
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
