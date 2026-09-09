import type { Metadata } from "next";

import { ServiceLanding } from "@/components/service-landing";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Electricidad en Ciudad Real | AUREA",
  description:
    "Servicios de electricidad en Ciudad Real capital y provincia: reparaciones, instalaciones, enchufes, puntos de luz, iluminación y cuadros eléctricos.",
  alternates: { canonical: "/servicios/electricidad" },
};

export default function ElectricalPage() {
  return (
    <ServiceLanding
      approach={[
        {
          title: "Entender la necesidad",
          description:
            "Conocer qué ocurre o qué se quiere instalar, sustituir o modificar.",
        },
        {
          title: "Valorar la instalación",
          description:
            "Revisar las características generales del espacio y del trabajo planteado.",
        },
        {
          title: "Plantear la actuación",
          description:
            "Organizar el trabajo de forma adecuada a la necesidad concreta.",
        },
      ]}
      approachText="Conocer la necesidad y las características generales de la instalación permite valorar el trabajo y plantear una actuación adecuada."
      approachTitle="Una actuación empieza por conocer la instalación"
      breadcrumb={[
        { label: "Servicios", href: "/servicios" },
        { label: "Electricidad" },
      ]}
      className={styles.page}
      contactLabel="Cuéntanos qué necesitas"
      contextualBlock={{
        eyebrow: "Electricidad en Ciudad Real",
        title: "Instalaciones y reparaciones eléctricas",
        text: "AUREA realiza trabajos de instalación y reparación eléctrica en Ciudad Real capital y provincia, atendiendo cada consulta según las características de la instalación y la necesidad planteada.",
        items: [
          {
            title: "Reparaciones eléctricas",
            description: "Actuaciones sobre elementos o instalaciones eléctricas que presentan una incidencia o necesitan reparación o sustitución.",
          },
          {
            title: "Instalaciones eléctricas",
            description: "Trabajos de instalación o modificación de elementos eléctricos según las necesidades del espacio.",
          },
          {
            title: "Enchufes, interruptores y puntos de luz",
            description: "Instalación, sustitución o reparación de enchufes, interruptores y puntos de luz.",
          },
          {
            title: "Iluminación y cuadros eléctricos",
            description: "Actuaciones relacionadas con elementos de iluminación y cuadros eléctricos según las necesidades de cada instalación.",
          },
        ],
      }}
      eyebrow="ELECTRICIDAD"
      finalContactLabel="Contactar con AUREA"
      finalText="Cuéntanos qué necesitas y las características generales de la instalación para que podamos conocer mejor tu consulta."
      finalTitle="¿Necesitas un trabajo de electricidad?"
      focusText="Cada instalación o incidencia puede requerir una actuación diferente. AUREA valora las necesidades del espacio y el trabajo eléctrico planteado antes de organizar la intervención."
      focusTitle="Trabajos eléctricos adaptados a cada necesidad"
      introduction="AUREA realiza trabajos de electricidad en Ciudad Real capital y provincia, tanto para reparaciones como para instalaciones y actuaciones sobre elementos habituales de una instalación eléctrica."
      sectionLabels={{
        focusEyebrow: "Electricidad",
        approachEyebrow: "Cómo se aborda cada trabajo",
      }}
      title="Servicios de electricidad en Ciudad Real"
      visualLabel="Electricidad AUREA"
      visualType="electricidad"
    />
  );
}
