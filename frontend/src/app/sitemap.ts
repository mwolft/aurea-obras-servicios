import type { MetadataRoute } from "next";

import { getRentalCategories, getToolPublicPath } from "@/lib/category-slug";
import { getCatalogTools } from "@/lib/api";
import { getPublicUrl } from "@/lib/site";

export const dynamic = "force-dynamic";

const staticPaths = ["/", "/servicios", "/servicios/jardineria", "/alquiler", "/contacto"];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticEntries = staticPaths.map((path) => ({ url: getPublicUrl(path) }));
  const catalog = await getCatalogTools();

  if (catalog.status !== "success") {
    return staticEntries;
  }

  const categoryEntries = getRentalCategories(catalog.tools).map((category) => ({
    url: getPublicUrl(`/alquiler/${category.slug}`),
  }));
  const toolEntries = catalog.tools.map((tool) => ({ url: getPublicUrl(getToolPublicPath(tool)) }));

  return [...staticEntries, ...categoryEntries, ...toolEntries];
}
