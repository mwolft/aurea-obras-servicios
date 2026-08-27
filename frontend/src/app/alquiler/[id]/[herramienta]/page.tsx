import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { RentalToolDetails } from "@/components/rental-tool-details";
import { getCategorySlug, getToolIdFromSlug, getToolPublicPath, getToolSlug } from "@/lib/category-slug";
import { getCatalogTool } from "@/lib/api";

import styles from "./page.module.css";

export const dynamic = "force-dynamic";

type RentalToolPublicPageProps = {
  params: Promise<{ id: string; herramienta: string }>;
};

async function getToolForPublicPath({ id: categorySlug, herramienta }: Awaited<RentalToolPublicPageProps["params"]>) {
  const toolId = getToolIdFromSlug(herramienta);

  if (toolId === null) {
    return { status: "not_found" as const };
  }

  const result = await getCatalogTool(toolId);

  if (result.status !== "success") {
    return result;
  }

  const { tool } = result;
  if (getCategorySlug(tool.category) !== categorySlug || getToolSlug(tool) !== herramienta) {
    return { status: "not_found" as const };
  }

  return result;
}

export async function generateMetadata({ params }: RentalToolPublicPageProps): Promise<Metadata> {
  const result = await getToolForPublicPath(await params);

  if (result.status !== "success") {
    return {};
  }

  const description = result.tool.description
    ? result.tool.description
    : `Consulta ${result.tool.name}, una herramienta de la categoría ${result.tool.category}.`;

  return {
    title: `${result.tool.name} | Alquiler | AUREA Obras y Servicios S.L.`,
    description,
    alternates: { canonical: getToolPublicPath(result.tool) },
  };
}

export default async function RentalToolPublicPage({ params }: RentalToolPublicPageProps) {
  const result = await getToolForPublicPath(await params);

  if (result.status === "not_found") {
    notFound();
  }

  if (result.status === "error") {
    return (
      <main className={styles.page}>
        <Link className={styles.backLink} href="/alquiler">← Volver al alquiler</Link>
        <section className={styles.message} role="alert">
          <h1>No podemos cargar esta herramienta.</h1>
          <p>Inténtalo de nuevo dentro de unos minutos.</p>
        </section>
      </main>
    );
  }

  return <RentalToolDetails tool={result.tool} />;
}
