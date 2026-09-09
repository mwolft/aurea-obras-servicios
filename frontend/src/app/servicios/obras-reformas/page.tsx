import type { Metadata } from "next";

import { ServiceLanding } from "@/components/service-landing";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Reformas en Ciudad Real | AUREA",
  description:
    "Obras y reformas en Ciudad Real capital y provincia. Cuéntanos tu proyecto y las necesidades del espacio para valorar la actuación con AUREA.",
  alternates: { canonical: "/servicios/obras-reformas" },
};

export default function WorksAndRenovationsPage() {
  return (
    <ServiceLanding
      approach={[
        {
          title: "Entender el proyecto",
          description:
            "Conocer qué se quiere realizar y las características generales del espacio.",
        },
        {
          title: "Valorar las necesidades",
          description:
            "Revisar las necesidades planteadas y definir el alcance de la actuación.",
        },
        {
          title: "Coordinar el trabajo",
          description:
            "Organizar la actuación de forma ordenada según el proyecto.",
        },
      ]}
      approachText="Conocer el espacio y el alcance del trabajo permite organizar la actuación de forma adecuada a cada proyecto."
      approachTitle="Una reforma empieza por entender bien el proyecto"
      breadcrumb={[
        { label: "Servicios", href: "/servicios" },
        { label: "Obras y reformas" },
      ]}
      className={styles.page}
      contactLabel="Cuéntanos tu proyecto"
      contextualBlock={{
        eyebrow: "Reformas en Ciudad Real",
        title: "Reformas para viviendas y otros espacios",
        text: "AUREA desarrolla proyectos de obra y reforma en Ciudad Real capital y provincia, tanto para actuaciones concretas como para trabajos de mayor alcance. Cada consulta se estudia según el espacio, las necesidades planteadas y el trabajo que sea necesario realizar.",
      }}
      eyebrow="OBRAS Y REFORMAS"
      finalText="Cuéntanos qué quieres hacer y las características generales del espacio para que podamos conocer mejor tu proyecto."
      finalTitle="¿Tienes un proyecto de obra o reforma?"
      focusText="Cada espacio y cada proyecto plantean necesidades diferentes. AUREA valora el trabajo a realizar para plantear una actuación acorde con las características y el alcance del proyecto."
      focusTitle="Obras y reformas adaptadas a cada proyecto"
      introduction="AUREA realiza obras y reformas en Ciudad Real capital y provincia, adaptando cada actuación a las necesidades del espacio y al alcance de cada proyecto."
      sectionLabels={{
        focusEyebrow: "Obras y reformas",
        approachEyebrow: "Cómo se aborda cada proyecto",
      }}
      title="Reformas en Ciudad Real"
      visualLabel="Obras y reformas AUREA"
      visualType="obras"
    />
  );
}
