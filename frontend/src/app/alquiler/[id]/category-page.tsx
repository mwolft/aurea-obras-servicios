import Link from "next/link";
import { notFound } from "next/navigation";

import { RentalToolCard } from "@/components/rental-tool-card";
import { getCategorySlug, getRentalCategory } from "@/lib/category-slug";
import { getCatalogTools } from "@/lib/api";

import styles from "./category-page.module.css";

type RentalCategoryContentProps = {
  slug: string;
};

export default async function RentalCategoryContent({ slug }: RentalCategoryContentProps) {
  const catalog = await getCatalogTools();

  if (catalog.status === "error") {
    return (
      <main className={styles.page}>
        <Link className={styles.backLink} href="/alquiler">← Volver al alquiler</Link>
        <section className={styles.feedback} role="alert">
          <h1>No podemos mostrar esta categoría ahora mismo.</h1>
          <p>Inténtalo de nuevo dentro de unos minutos.</p>
        </section>
      </main>
    );
  }

  const category = getRentalCategory(catalog.tools, slug);

  if (!category) {
    notFound();
  }

  const tools = catalog.tools.filter((tool) => getCategorySlug(tool.category) === category.slug);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <nav aria-label="Migas de pan" className={styles.breadcrumbs}>
          <ol>
            <li><Link className={styles.backLink} href="/alquiler">Alquiler</Link></li>
            <li aria-current="page">{category.name}</li>
          </ol>
        </nav>
        <p className={styles.eyebrow}>Alquiler de herramientas</p>
        <h1>{category.name}</h1>
        <p>Consulta las herramientas disponibles en esta categoría.</p>
      </header>

      <section aria-label={`Herramientas de ${category.name}`} className={styles.grid}>
        {tools.map((tool) => <RentalToolCard key={tool.id} tool={tool} />)}
      </section>
    </main>
  );
}
