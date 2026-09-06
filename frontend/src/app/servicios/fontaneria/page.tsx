import type { Metadata } from "next";

import { ServiceLanding } from "@/components/service-landing";
import { legalInfo } from "@/lib/legal";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: `Fontanería | ${legalInfo.companyName}`,
  description:
    "Servicios de fontanería de AUREA para valorar cada necesidad según las características del espacio.",
  alternates: { canonical: "/servicios/fontaneria" },
};

export default function PlumbingPage() {
  return (
    <ServiceLanding
      approach={[
        {
          title: "Conocer la consulta",
          description:
            "Partimos de entender qué necesitas y el contexto del espacio antes de plantear el trabajo.",
        },
        {
          title: "Valorar el caso",
          description:
            "Cada necesidad se estudia de forma práctica para orientar la intervención adecuada.",
        },
        {
          title: "Ordenar el trabajo",
          description:
            "La actuación se plantea de forma clara y coordinada según las necesidades identificadas.",
        },
      ]}
      approachText="Una consulta clara permite valorar el espacio y plantear el trabajo de fontanería de manera ordenada."
      approachTitle="Cada trabajo empieza por entender lo que necesita el espacio."
      className={styles.page}
      contactLabel="Cuéntanos qué necesitas"
      eyebrow="Fontanería"
      finalText="Explícanos tu consulta para que podamos conocer mejor el espacio y la necesidad que planteas."
      finalTitle="¿Tienes una necesidad de fontanería?"
      focusText="AUREA aborda trabajos de fontanería a partir de una valoración previa, atendiendo a las necesidades concretas de viviendas, negocios y otros espacios."
      focusTitle="Una intervención adaptada a cada necesidad."
      introduction="AUREA presta servicios de fontanería con una forma de trabajo práctica, ordenada y ajustada a cada consulta."
      title="Servicios de fontanería para viviendas, negocios y otros espacios."
      visualLabel="Fontanería AUREA"
      visualType="fontaneria"
    />
  );
}
