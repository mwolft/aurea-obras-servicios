import Link from "next/link";

import AvailabilityChecker from "@/app/alquiler/[id]/availability-checker";
import { getCategorySlug } from "@/lib/category-slug";
import type { CatalogTool } from "@/lib/api";
import { getRentalProductPageContent } from "@/lib/rental-product-content";

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
      <span>Sin imagen disponible</span>
    </div>
  );
}

export function RentalToolDetails({ tool }: RentalToolDetailsProps) {
  const [mainImage, ...secondaryImages] = tool.images;
  const categoryPath = `/alquiler/${getCategorySlug(tool.category)}`;
  const content = getRentalProductPageContent(tool);
  const formatAmount = (amount: string) =>
    new Intl.NumberFormat("es-ES", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(amount));
  const depositNotice = content.depositNotice?.replace("{amount}", `${formatAmount(tool.deposit_amount)} €`);

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
            <img alt={content.imageAlt} className={styles.mainImage} src={mainImage.url} />
          ) : <ToolPlaceholder />}
          {secondaryImages.length > 0 && <div className={styles.secondaryImages}>{secondaryImages.map((image) => (
            // Cloudinary supplies a public HTTPS URL; no remote image config is needed.
            // eslint-disable-next-line @next/next/no-img-element
            <img alt={`${tool.name} — imagen ${image.position + 1}`} className={styles.secondaryImage} key={image.position} src={image.url} />
          ))}</div>}
        </section>

        <div className={styles.overview}>
          <p className={styles.category}>{content.eyebrow}</p>
          <p className={tool.is_available ? styles.available : styles.unavailable}>{tool.is_available ? "Disponible" : "No disponible"}</p>
          <h1>{content.h1}</h1>
          {content.intro && <p className={styles.description}>{content.intro}</p>}
          <div className={styles.pricePanel}><div><span>{content.priceLabel}</span><strong>{formatAmount(tool.daily_price)} € <small>/ día</small></strong></div><div><span>Fianza</span><strong>{formatAmount(tool.deposit_amount)} €</strong>{depositNotice && <small className={styles.depositNotice}>{depositNotice}</small>}</div></div>
          <section className={styles.fulfillment}><h2>Recogida y transporte</h2><ul>
            <li><strong>Recogida en almacén</strong><span>{tool.pickup_available ? "Disponible" : "No disponible"}</span></li>
            <li><strong>Transporte</strong><span>{tool.delivery_available ? "Disponible" : "No disponible"}{tool.delivery_available && tool.delivery_price_per_km ? ` · ${formatAmount(tool.delivery_price_per_km)} €/km` : ""}</span></li>
            {tool.included_km !== null && <li><strong>Kilómetros incluidos</strong><span>{tool.included_km}</span></li>}
            {tool.extra_km_price !== null && <li><strong>Precio por km excedido</strong><span>{formatAmount(tool.extra_km_price)} €</span></li>}
          </ul></section>
          {content.transportNotice && <p className={styles.transportNotice}>{content.transportNotice}</p>}
        </div>
      </article>
      <AvailabilityChecker deliveryAvailable={tool.delivery_available} pickupAvailable={tool.pickup_available} toolId={tool.id} />
      {content.editorialHeading && content.editorialContent && (
        <section aria-labelledby="rental-product-editorial" className={styles.editorial}>
          <h2 id="rental-product-editorial">{content.editorialHeading}</h2>
          {content.editorialContent.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
          {content.categoryLinkLabel && <Link className={styles.categoryLink} href={categoryPath}>{content.categoryLinkLabel}</Link>}
        </section>
      )}
    </main>
  );
}
