import Link from "next/link";

import { getToolPublicPath } from "@/lib/category-slug";
import type { CatalogTool } from "@/lib/api";

import styles from "./rental-tool-card.module.css";

type RentalToolCardProps = {
  tool: CatalogTool;
};

function ToolPlaceholder() {
  return (
    <div aria-label="Imagen de herramienta no disponible" className={styles.placeholder} role="img">
      <svg aria-hidden="true" viewBox="0 0 48 48">
        <path d="m30 10 8 8-10 10-8-8 10-10ZM22 18 10 30l8 8 12-12M10 14l8 8m-8 0 10-10" />
      </svg>
      <span>Imagen próximamente</span>
    </div>
  );
}

export function RentalToolCard({ tool }: RentalToolCardProps) {
  const mainImage = tool.images[0];

  return (
    <article className={styles.card}>
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
          <Link className={styles.detailLink} href={getToolPublicPath(tool)}>Ver herramienta</Link>
        </div>
      </div>
    </article>
  );
}
