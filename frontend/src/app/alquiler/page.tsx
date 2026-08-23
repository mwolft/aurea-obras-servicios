import Link from "next/link";

import { getCatalogTools } from "@/lib/api";

import styles from "./page.module.css";

export const dynamic = "force-dynamic";

function ToolPlaceholder() {
  return (
    <div aria-label="Imagen de herramienta no disponible" className={styles.placeholder} role="img">
      <svg aria-hidden="true" viewBox="0 0 48 48"><path d="m30 10 8 8-10 10-8-8 10-10ZM22 18 10 30l8 8 12-12M10 14l8 8m-8 0 10-10" /></svg>
      <span>Imagen próximamente</span>
    </div>
  );
}

export default async function RentalCatalogPage() {
  const catalog = await getCatalogTools();

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
        <section aria-label="Herramientas de alquiler" className={styles.grid}>
          {catalog.tools.map((tool) => {
            const mainImage = tool.images[0];

            return (
              <article className={styles.card} key={tool.id}>
                <div className={styles.media}>
                  {mainImage ? (
                    // Cloudinary supplies a public HTTPS URL; no remote image config is needed.
                    // eslint-disable-next-line @next/next/no-img-element
                    <img alt={tool.name} className={styles.image} src={mainImage.url} />
                  ) : <ToolPlaceholder />}
                  <p className={tool.is_available ? styles.available : styles.unavailable}>
                    {tool.is_available ? "Disponible" : "No disponible"}
                  </p>
                </div>
                <div className={styles.content}>
                  <p className={styles.category}>{tool.category}</p>
                  <h2>{tool.name}</h2>
                  {tool.description && <p className={styles.description}>{tool.description}</p>}
                  <div className={styles.cardFooter}>
                    <p className={styles.price}><strong>{tool.daily_price} €</strong><span>/ día</span></p>
                    <Link className={styles.detailLink} href={`/alquiler/${tool.id}`}>Ver herramienta</Link>
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
