import { getCatalogTools } from "@/lib/api";

import styles from "./page.module.css";

export const dynamic = "force-dynamic";

export default async function RentalCatalogPage() {
  const catalog = await getCatalogTools();

  return (
    <main>
      <header className={styles.header}>
        <p className={styles.eyebrow}>Catálogo</p>
        <h1>Alquiler de herramientas</h1>
        <p>Consulta las herramientas disponibles para alquilar.</p>
      </header>

      {catalog.status === "error" ? (
        <p className={styles.message} role="alert">
          No podemos cargar el catálogo en este momento. Inténtalo de nuevo más tarde.
        </p>
      ) : catalog.tools.length === 0 ? (
        <p className={styles.message}>No hay herramientas publicadas en este momento.</p>
      ) : (
        <section aria-label="Herramientas disponibles" className={styles.grid}>
          {catalog.tools.map((tool) => {
            const mainImage = tool.images[0];

            return (
              <article className={styles.card} key={tool.id}>
                {mainImage ? (
                  // Cloudinary already supplies a public, HTTPS image URL.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img alt={tool.name} className={styles.image} src={mainImage.url} />
                ) : (
                  <div aria-label="Imagen no disponible" className={styles.placeholder} role="img">
                    Sin imagen
                  </div>
                )}

                <div className={styles.content}>
                  <p className={styles.category}>{tool.category}</p>
                  <h2>{tool.name}</h2>
                  {tool.description && <p className={styles.description}>{tool.description}</p>}
                  <p className={styles.price}>{tool.daily_price} € / día</p>
                  <p className={tool.is_available ? styles.available : styles.unavailable}>
                    {tool.is_available ? "Disponible" : "No disponible"}
                  </p>
                  <ul className={styles.options}>
                    <li>Recogida: {tool.pickup_available ? "disponible" : "no disponible"}</li>
                    <li>
                      Transporte: {tool.delivery_available ? "disponible" : "no disponible"}
                      {tool.delivery_available && tool.delivery_price_per_km
                        ? ` (${tool.delivery_price_per_km} €/km)`
                        : ""}
                    </li>
                  </ul>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
