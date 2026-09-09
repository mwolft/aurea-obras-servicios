import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";

import { getRentalCategory, getToolPublicPath } from "@/lib/category-slug";
import { getCatalogTool, getCatalogTools } from "@/lib/api";
import { getRentalCategoryPageContent } from "@/lib/rental-category-content";

import RentalCategoryContent from "./category-page";
import categoryStyles from "./category-page.module.css";

export const dynamic = "force-dynamic";

type RentalToolPageProps = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: RentalToolPageProps): Promise<Metadata> {
  const { id } = await params;
  const toolId = Number(id);

  if (Number.isSafeInteger(toolId) && toolId > 0) {
    return { robots: { index: false, follow: true } };
  }

  const catalog = await getCatalogTools();
  const category = catalog.status === "success" ? getRentalCategory(catalog.tools, id) : undefined;

  if (!category) {
    return {};
  }

  const content = getRentalCategoryPageContent(category);

  return {
    title: content.metadata?.title ?? `${category.name} de alquiler | AUREA`,
    description:
      content.metadata?.description ??
      `Consulta las herramientas disponibles en la categoría ${category.name} de AUREA.`,
    alternates: { canonical: `/alquiler/${category.slug}` },
  };
}

export default async function RentalToolPage({ params }: RentalToolPageProps) {
  const { id } = await params;
  const toolId = Number(id);

  if (!Number.isSafeInteger(toolId) || toolId < 1) {
    return <RentalCategoryContent slug={id} />;
  }

  const result = await getCatalogTool(toolId);
  if (result.status === "not_found") notFound();
  if (result.status === "error") {
    return (
      <main className={categoryStyles.page}>
        <Link className={categoryStyles.backLink} href="/alquiler">← Volver al alquiler</Link>
        <section className={categoryStyles.feedback} role="alert">
          <h1>No podemos cargar esta herramienta.</h1>
          <p>Inténtalo de nuevo dentro de unos minutos.</p>
        </section>
      </main>
    );
  }

  permanentRedirect(getToolPublicPath(result.tool));
}
