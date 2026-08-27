import type { Metadata } from "next";
import Link from "next/link";

import { RentalToolCard } from "@/components/rental-tool-card";
import { getRentalCategories } from "@/lib/category-slug";
import { getCatalogTools } from "@/lib/api";

import styles from "./page.module.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Alquiler de herramientas | AUREA Obras y Servicios S.L.",
  description: "Consulta el catálogo público de herramientas de alquiler de AUREA Obras y Servicios S.L.",
  alternates: { canonical: "/alquiler" },
};

export default async function RentalCatalogPage() {
  const catalog = await getCatalogTools();
  const categories = catalog.status === "success" ? getRentalCategories(catalog.tools) : [];

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>Alquiler de herramientas</p>
        <h1>Encuentra la herramienta que necesitas.</h1>
        <p>Consulta cada ficha para comprobar la disponibilidad en las fechas que mejor te encajen.</p>
      </header>

      {catalog.status === "error" ? (
        <section className={`${styles.feedback} ${styles.error}`} role="alert">
          <h2>No podemos mostrar el catálogo ahora mismo.</h2>
          <p>Inténtalo de nuevo dentro de unos minutos.</p>
        </section>
      ) : catalog.tools.length === 0 ? (
        <section className={styles.feedback}>
          <h2>Estamos preparando el catálogo.</h2>
          <p>Aún no hay herramientas publicadas. Vuelve a consultar esta sección próximamente.</p>
        </section>
      ) : (
        <>
          <section aria-labelledby="categories-title" className={styles.categories}>
            <h2 id="categories-title">Explorar por categoría</h2>
            <div className={styles.categoryLinks}>
              {categories.map((category) => (
                <Link href={`/alquiler/${category.slug}`} key={category.slug}>{category.name}</Link>
              ))}
            </div>
          </section>
          <section aria-label="Herramientas de alquiler" className={styles.grid}>
            {catalog.tools.map((tool) => <RentalToolCard key={tool.id} tool={tool} />)}
          </section>
        </>
      )}
    </main>
  );
}
