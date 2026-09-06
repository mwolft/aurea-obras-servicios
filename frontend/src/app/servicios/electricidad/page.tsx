import type { Metadata } from "next";

import { ServiceLanding } from "@/components/service-landing";
import { legalInfo } from "@/lib/legal";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: `Electricidad | ${legalInfo.companyName}`,
  description:
    "Servicios de electricidad de AUREA, planteados según las necesidades de cada espacio y consulta.",
  alternates: { canonical: "/servicios/electricidad" },
};

export default function ElectricalPage() {
  return (
    <ServiceLanding
      approach={[
        {
          title: "Escuchar la necesidad",
          description:
            "La consulta comienza por conocer qué necesita el espacio y qué contexto presenta el trabajo.",
        },
        {
          title: "Valorar el espacio",
          description:
            "La planificación se orienta a las características concretas de cada vivienda, negocio u otro entorno.",
        },
        {
          title: "Coordinar la actuación",
          description:
            "El trabajo se organiza de forma clara para abordar la necesidad planteada de manera ordenada.",
        },
      ]}
      approachText="Cada caso requiere una conversación previa para conocer el espacio y plantear el trabajo de forma adecuada."
      approachTitle="Una forma de trabajar clara desde la primera consulta."
      className={styles.page}
      contactLabel="Cuéntanos qué necesitas"
      eyebrow="Electricidad"
      finalText="Cuéntanos qué necesitas para que podamos conocer mejor tu consulta y el espacio al que se refiere."
      finalTitle="¿Quieres plantearnos una necesidad eléctrica?"
      focusText="AUREA ofrece servicios de electricidad adaptados a las necesidades de cada espacio, con una intervención planificada y una coordinación ordenada."
      focusTitle="Cada espacio plantea una necesidad distinta."
      introduction="AUREA aborda consultas de electricidad desde la valoración previa y la planificación de cada trabajo."
      title="Servicios de electricidad adaptados a cada espacio."
      visualLabel="Electricidad AUREA"
      visualType="electricidad"
    />
  );
}
