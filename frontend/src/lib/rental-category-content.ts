import type { RentalCategory } from "./category-slug";

type RentalCategoryPageContent = {
  eyebrow: string;
  heading: string;
  introduction: string;
  catalogHeading?: string;
  metadata?: {
    title: string;
    description: string;
  };
};

const categoryContentBySlug: Record<string, RentalCategoryPageContent> = {
  maquinaria: {
    eyebrow: "Alquiler de maquinaria",
    heading: "Alquiler de maquinaria en Ciudad Real",
    introduction:
      "Consulta la maquinaria disponible para alquiler en Ciudad Real capital y provincia. Accede a cada ficha para conocer sus características, precio y disponibilidad.",
    catalogHeading: "Maquinaria disponible para alquilar",
    metadata: {
      title: "Alquiler de maquinaria en Ciudad Real | AUREA",
      description:
        "Alquiler de maquinaria en Ciudad Real capital y provincia. Consulta la maquinaria disponible, precios y disponibilidad en AUREA.",
    },
  },
  herramientas: {
    eyebrow: "Alquiler de herramientas",
    heading: "Alquiler de herramientas en Ciudad Real",
    introduction:
      "Consulta las herramientas disponibles para alquiler en Ciudad Real capital y provincia. Accede a cada ficha para conocer sus características, precio y disponibilidad.",
    catalogHeading: "Herramientas disponibles para alquilar",
    metadata: {
      title: "Alquiler de herramientas en Ciudad Real | AUREA",
      description:
        "Alquiler de herramientas en Ciudad Real capital y provincia. Consulta las herramientas disponibles, precios y disponibilidad en AUREA.",
    },
  },
};

export function getRentalCategoryPageContent(
  category: RentalCategory,
): RentalCategoryPageContent {
  return (
    categoryContentBySlug[category.slug] ?? {
      eyebrow: "Alquiler de herramientas",
      heading: category.name,
      introduction: "Consulta las herramientas disponibles en esta categoría.",
    }
  );
}
