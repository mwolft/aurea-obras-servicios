import type { Metadata } from "next";

import { ServiceLanding } from "@/components/service-landing";

import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Fontanería en Ciudad Real | AUREA",
  description:
    "Servicios de fontanería en Ciudad Real capital y provincia: reparaciones, instalaciones, tuberías, fugas de agua y grifería. Contacta con AUREA.",
  alternates: { canonical: "/servicios/fontaneria" },
};

export default function PlumbingPage() {
  return (
    <ServiceLanding
      approach={[
        {
          title: "Entender la necesidad",
          description:
            "Conocer qué ocurre o qué se quiere instalar o modificar.",
        },
        {
          title: "Valorar la instalación",
          description:
            "Revisar las características generales de la instalación y el trabajo necesario.",
        },
        {
          title: "Plantear la actuación",
          description:
            "Organizar el trabajo de forma adecuada a la necesidad planteada.",
        },
      ]}
      approachText="Conocer el problema o el trabajo que se quiere realizar permite valorar la instalación y plantear una actuación adecuada."
      approachTitle="Una actuación empieza por conocer la necesidad"
      breadcrumb={[
        { label: "Servicios", href: "/servicios" },
        { label: "Fontanería" },
      ]}
      className={styles.page}
      contactLabel="Cuéntanos qué necesitas"
      contextualBlock={{
        eyebrow: "Fontanería en Ciudad Real",
        title: "Reparaciones e instalaciones de fontanería",
        text: "AUREA realiza trabajos de reparación e instalación de fontanería en Ciudad Real capital y provincia, atendiendo cada consulta según las características de la instalación y la necesidad planteada.",
        items: [
          {
            title: "Reparaciones de fontanería",
            description: "Actuaciones relacionadas con incidencias y elementos de fontanería que necesitan reparación o sustitución.",
          },
          {
            title: "Instalaciones de fontanería",
            description: "Trabajos de instalación de elementos y conducciones de fontanería según las necesidades del espacio.",
          },
          {
            title: "Tuberías y fugas de agua",
            description: "Actuaciones sobre tuberías y fugas de agua cuando la instalación requiere revisión o reparación.",
          },
          {
            title: "Grifería y elementos de fontanería",
            description: "Instalación, sustitución o reparación de grifería y otros elementos habituales de fontanería.",
          },
        ],
      }}
      eyebrow="FONTANERÍA"
      finalContactLabel="Contactar con AUREA"
      finalText="Cuéntanos qué necesitas y las características generales de la instalación para que podamos conocer mejor tu consulta."
      finalTitle="¿Necesitas un trabajo de fontanería?"
      focusText="Cada instalación o incidencia puede requerir una actuación diferente. AUREA valora las necesidades del espacio y el trabajo de fontanería necesario antes de plantear la intervención."
      focusTitle="Trabajos de fontanería adaptados a cada necesidad"
      introduction="AUREA realiza trabajos de fontanería en Ciudad Real capital y provincia, tanto para reparaciones como para instalaciones y actuaciones relacionadas con tuberías, fugas de agua y elementos habituales de fontanería."
      sectionLabels={{
        focusEyebrow: "Fontanería",
        approachEyebrow: "Cómo se aborda cada trabajo",
      }}
      title="Servicios de fontanería en Ciudad Real"
      visualLabel="Fontanería AUREA"
      visualType="fontaneria"
    />
  );
}
