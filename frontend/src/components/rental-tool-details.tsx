import Link from "next/link";

import AvailabilityChecker from "@/app/alquiler/[id]/availability-checker";
import { getCategorySlug } from "@/lib/category-slug";
import type { CatalogTool } from "@/lib/api";

import styles from "./rental-tool-details.module.css";

type RentalToolDetailsProps = {
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

export function RentalToolDetails({ tool }: RentalToolDetailsProps) {
  const [mainImage, ...secondaryImages] = tool.images;
  const categoryPath = `/alquiler/${getCategorySlug(tool.category)}`;

  return (
    <main className={styles.page}>
      <nav aria-label="Migas de pan" className={styles.breadcrumbs}>
        <ol>
          <li><Link href="/alquiler">Alquiler</Link></li>
          <li><Link href={categoryPath}>{tool.category}</Link></li>
          <li aria-current="page">{tool.name}</li>
        </ol>
      </nav>

      <article className={styles.product}>
        <section aria-label={`Imágenes de ${tool.name}`} className={styles.gallery}>
          {mainImage ? (
            // Cloudinary supplies a public HTTPS URL; no remote image config is needed.
            // eslint-disable-next-line @next/next/no-img-element
            <img alt={`${tool.name} — imagen principal`} className={styles.mainImage} src={mainImage.url} />
          ) : <ToolPlaceholder />}
          {secondaryImages.length > 0 && <div className={styles.secondaryImages}>{secondaryImages.map((image) => (
            // Cloudinary supplies a public HTTPS URL; no remote image config is needed.
            // eslint-disable-next-line @next/next/no-img-element
            <img alt={`${tool.name} — imagen ${image.position + 1}`} className={styles.secondaryImage} key={image.position} src={image.url} />
          ))}</div>}
        </section>

        <div className={styles.overview}>
          <p className={styles.category}>{tool.category}</p>
          <p className={tool.is_available ? styles.available : styles.unavailable}>{tool.is_available ? "Disponible" : "No disponible"}</p>
          <h1>{tool.name}</h1>
          {tool.description && <p className={styles.description}>{tool.description}</p>}
          <div className={styles.pricePanel}><div><span>Precio de alquiler</span><strong>{tool.daily_price} € <small>/ día</small></strong></div><div><span>Fianza</span><strong>{tool.deposit_amount} €</strong></div></div>
          <section className={styles.fulfillment}><h2>Recogida y transporte</h2><ul>
            <li><strong>Recogida en almacén</strong><span>{tool.pickup_available ? "Disponible" : "No disponible"}</span></li>
            <li><strong>Transporte</strong><span>{tool.delivery_available ? "Disponible" : "No disponible"}{tool.delivery_available && tool.delivery_price_per_km ? ` · ${tool.delivery_price_per_km} €/km` : ""}</span></li>
            {tool.included_km !== null && <li><strong>Kilómetros incluidos</strong><span>{tool.included_km}</span></li>}
            {tool.extra_km_price !== null && <li><strong>Precio por km excedido</strong><span>{tool.extra_km_price} €</span></li>}
          </ul></section>
        </div>
      </article>
      <AvailabilityChecker deliveryAvailable={tool.delivery_available} pickupAvailable={tool.pickup_available} toolId={tool.id} />
    </main>
  );
}
