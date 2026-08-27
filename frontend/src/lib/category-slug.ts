import type { CatalogTool } from "./api";

export type RentalCategory = {
  name: string;
  slug: string;
};

export function getCategorySlug(category: string): string {
  return category
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es-ES")
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function getRentalCategories(tools: CatalogTool[]): RentalCategory[] {
  const categoriesBySlug = new Map<string, RentalCategory>();

  for (const tool of tools) {
    const slug = getCategorySlug(tool.category);

    if (slug && !categoriesBySlug.has(slug)) {
      categoriesBySlug.set(slug, { name: tool.category, slug });
    }
  }

  return [...categoriesBySlug.values()].sort((left, right) =>
    left.name.localeCompare(right.name, "es-ES"),
  );
}

export function getRentalCategory(tools: CatalogTool[], slug: string): RentalCategory | undefined {
  return getRentalCategories(tools).find((category) => category.slug === slug);
}

export function getToolSlug(tool: Pick<CatalogTool, "id" | "name">): string {
  const nameSlug = getCategorySlug(tool.name);

  return `${nameSlug || "herramienta"}-${tool.id}`;
}

export function getToolIdFromSlug(slug: string): number | null {
  const match = /-(\d+)$/.exec(slug);

  if (!match) {
    return null;
  }

  const id = Number(match[1]);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

export function getToolPublicPath(tool: Pick<CatalogTool, "id" | "name" | "category">): string {
  return `/alquiler/${getCategorySlug(tool.category)}/${getToolSlug(tool)}`;
}
