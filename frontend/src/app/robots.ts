import type { MetadataRoute } from "next";

import { getPublicUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/admin/", "/login", "/mi-cuenta/"],
    },
    sitemap: getPublicUrl("/sitemap.xml"),
  };
}
