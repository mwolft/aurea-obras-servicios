import type { Metadata } from "next";

import { ServiceLanding } from "@/components/service-landing";
import { legalInfo } from "@/lib/legal";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: `Obras y reformas | ${legalInfo.companyName}`,
  description:
    "Obras y reformas de AUREA, planteadas de forma ordenada y adaptada a cada proyecto y espacio.",
  alternates: { canonical: "/servicios/obras-reformas" },
};

export default function WorksAndRenovationsPage() {
  return (
    <ServiceLanding
      approach={[
        {
          title: "Entender el proyecto",
          description:
            "Cada obra o reforma parte de conocer la idea, el espacio y las necesidades planteadas.",
        },
        {
          title: "Valorar las necesidades",
          description:
            "La planificación se adapta al caso concreto antes de ordenar los trabajos necesarios.",
        },
        {
          title: "Coordinar el trabajo",
          description:
            "La ejecución se plantea de forma organizada para avanzar con una visión clara del proyecto.",
        },
      ]}
      approachText="Conocer cada proyecto permite orientar el trabajo y organizar la actuación según las necesidades reales del espacio."
      approachTitle="Un proyecto se construye desde una planificación clara."
      className={styles.page}
      contactLabel="Cuéntanos tu proyecto"
      eyebrow="Obras y reformas"
      finalText="Explícanos tu proyecto para que podamos conocer el espacio y las necesidades que quieres plantear."
      finalTitle="¿Tienes un proyecto de obra o reforma?"
      focusText="AUREA aborda obras y reformas desde el estudio previo, la planificación y la coordinación de los trabajos según cada proyecto."
      focusTitle="Cada proyecto necesita una forma de trabajo propia."
      introduction="AUREA realiza obras y reformas adaptadas a cada proyecto, atendiendo a las necesidades concretas de cada espacio."
      title="Obras y reformas adaptadas a cada proyecto."
      visualLabel="Obras y reformas AUREA"
      visualType="obras"
    />
  );
}
