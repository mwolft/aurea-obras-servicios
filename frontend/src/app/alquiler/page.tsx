import type { Metadata } from "next";
import Link from "next/link";

import { RentalToolCard } from "@/components/rental-tool-card";
import { getRentalCategories } from "@/lib/category-slug";
import { getCatalogTools } from "@/lib/api";

import styles from "./page.module.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Alquiler de maquinaria y herramientas en Ciudad Real | AUREA",
  description:
    "Alquiler de maquinaria y herramientas en Ciudad Real capital y provincia. Consulta el catálogo de AUREA, precios y disponibilidad de cada equipo.",
  alternates: { canonical: "/alquiler" },
};

export default async function RentalCatalogPage() {
  const catalog = await getCatalogTools();
  const categories = catalog.status === "success" ? getRentalCategories(catalog.tools) : [];

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>Alquiler</p>
        <h1>Alquiler de maquinaria y herramientas en Ciudad Real</h1>
        <p>
          Consulta la maquinaria y las herramientas disponibles para alquiler en Ciudad Real
          capital y provincia. Accede a cada ficha para conocer sus características, precio y
          disponibilidad.
        </p>
      </header>

      {catalog.status === "error" ? (
        <section className={`${styles.feedback} ${styles.error}`} role="alert">
          <h2>No podemos mostrar el catálogo ahora mismo.</h2>
          <p>Inténtalo de nuevo dentro de unos minutos.</p>
        </section>
      ) : catalog.tools.length === 0 ? (
        <section className={styles.feedback}>
          <h2>No hay equipos disponibles en este momento</h2>
          <p>Actualmente no hay maquinaria ni herramientas publicadas para alquiler.</p>
        </section>
      ) : (
        <>
          <section aria-labelledby="categories-title" className={styles.categories}>
            <h2 id="categories-title">¿Qué necesitas alquilar?</h2>
            <div className={styles.categoryLinks}>
              {categories.map((category) => (
                <Link href={`/alquiler/${category.slug}`} key={category.slug}>{category.name}</Link>
              ))}
            </div>
          </section>
          <section aria-labelledby="catalog-title" className={styles.catalog}>
            <h2 id="catalog-title">Maquinaria y herramientas disponibles</h2>
            <div className={styles.grid}>
              {catalog.tools.map((tool) => <RentalToolCard key={tool.id} tool={tool} />)}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
