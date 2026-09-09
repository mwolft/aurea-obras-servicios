import type { CatalogTool } from "./api";

type RentalProductContentOverride = {
  eyebrow?: string;
  h1?: string;
  intro?: string;
  editorialHeading?: string;
  editorialContent?: string[];
  metaTitle?: string;
  metaDescription?: string;
  imageAlt?: string;
  priceLabel?: string;
  depositNotice?: string;
  transportNotice?: string;
  categoryLinkLabel?: string;
};

export type RentalProductPageContent = {
  eyebrow: string;
  h1: string;
  intro: string | null;
  imageAlt: string;
  priceLabel: string;
  editorialHeading?: string;
  editorialContent?: string[];
  metaTitle?: string;
  metaDescription?: string;
  depositNotice?: string;
  transportNotice?: string;
  categoryLinkLabel?: string;
};

const productContentById: Record<number, RentalProductContentOverride> = {
  13: {
    eyebrow: "MINI RETROEXCAVADORA",
    h1: "Alquiler de miniexcavadora en Ciudad Real",
    intro:
      "Alquila esta mini retroexcavadora en Ciudad Real capital y provincia. Su formato compacto está pensado para trabajos de excavación, movimiento de tierra y pequeñas obras en espacios reducidos. Consulta las fechas disponibles y las opciones de recogida o transporte.",
    editorialHeading: "Alquiler de mini excavadora en Ciudad Real",
    editorialContent: [
      "Esta mini retroexcavadora está disponible para alquiler en Ciudad Real capital y provincia. Es una máquina compacta destinada a trabajos de excavación, movimiento de tierra y pequeñas obras, especialmente cuando el espacio disponible es reducido.",
      "La reserva se realiza seleccionando primero las fechas. El sistema comprobará la disponibilidad real para el periodo elegido antes de continuar con la solicitud.",
      "La recogida en almacén está disponible. También puede solicitarse transporte, cuyo importe se revisa según la distancia antes de confirmar la reserva.",
    ],
    metaTitle: "Alquiler de miniexcavadora en Ciudad Real | AUREA",
    metaDescription:
      "Alquiler de mini retroexcavadora en Ciudad Real capital y provincia. Consulta precio, disponibilidad, recogida y transporte.",
    imageAlt: "Mini retroexcavadora de alquiler en Ciudad Real",
    priceLabel: "Precio de alquiler por día",
    depositNotice:
      "Se solicitará una autorización temporal de {amount} en concepto de fianza durante el proceso de alquiler.",
    transportNotice:
      "El transporte se calcula según la distancia y requiere revisión antes de confirmar el importe final.",
    categoryLinkLabel: "Ver más maquinaria de alquiler",
  },
};

/**
 * Returns presentation and SEO copy for an individual public rental page.
 * Product data, availability and pricing remain supplied by the backend.
 */
export function getRentalProductPageContent(tool: CatalogTool): RentalProductPageContent {
  const override = productContentById[tool.id];

  return {
    eyebrow: override?.eyebrow ?? tool.category,
    h1: override?.h1 ?? tool.name,
    intro: override?.intro ?? tool.description,
    editorialHeading: override?.editorialHeading,
    editorialContent: override?.editorialContent,
    metaTitle: override?.metaTitle,
    metaDescription: override?.metaDescription,
    imageAlt: override?.imageAlt ?? `${tool.name} — imagen principal`,
    priceLabel: override?.priceLabel ?? "Precio de alquiler",
    depositNotice: override?.depositNotice,
    transportNotice: override?.transportNotice,
    categoryLinkLabel: override?.categoryLinkLabel,
  };
}
