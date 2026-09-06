import type { Metadata } from "next";
import Link from "next/link";

import styles from "../legal-page.module.css";
import { legalInfo } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Política de privacidad | AUREA Obras y Servicios",
  description: "Información sobre el tratamiento de datos personales en la web de AUREA Obras y Servicios.",
  alternates: { canonical: "/politica-de-privacidad" },
};

export default function PrivacyPolicyPage() {
  return (
    <main className={styles.page}>
      <header className={styles.hero}>
        <p className={styles.eyebrow}>Información legal</p>
        <h1>Política de privacidad</h1>
        <p>
          Esta política explica cómo AUREA trata los datos personales que se facilitan al utilizar la web, crear una cuenta o solicitar una reserva.
        </p>
      </header>

      <div className={styles.content}>
        <section aria-labelledby="privacy-controller">
          <h2 id="privacy-controller">Responsable del tratamiento</h2>
          <article className={styles.legalCard}>
            <dl>
              <div><dt>Responsable</dt><dd>{legalInfo.controller}</dd></div>
              <div><dt>CIF</dt><dd>{legalInfo.taxId}</dd></div>
              <div><dt>Domicilio</dt><dd>{legalInfo.address}</dd></div>
              <div><dt>Contacto</dt><dd><a href={`mailto:${legalInfo.legalEmail}`}>{legalInfo.legalEmail}</a></dd></div>
            </dl>
          </article>
        </section>

        <section aria-labelledby="privacy-data">
          <h2 id="privacy-data">Datos que podemos tratar</h2>
          <h3>Consultas de contacto</h3>
          <p>Nombre, email, teléfono y asunto cuando se facilitan, junto con el contenido del mensaje.</p>
          <h3>Cuenta de usuario</h3>
          <p>Nombre, email, hash de contraseña cuando se utiliza el acceso local e identificador de Google cuando se inicia sesión mediante OAuth.</p>
          <h3>Reservas de herramientas</h3>
          <p>Datos de contacto, fechas, herramienta solicitada, modalidad, dirección de entrega cuando corresponde, importes y datos operativos de la reserva, además de la constancia de aceptación de condiciones y privacidad.</p>
          <p>AUREA no solicita ni almacena actualmente números de tarjeta, datos bancarios, DNI ni documentos de identidad a través de estos flujos.</p>
        </section>

        <section aria-labelledby="privacy-purposes">
          <h2 id="privacy-purposes">Finalidades y bases del tratamiento</h2>
          <ul>
            <li>Atender las consultas que una persona envía voluntariamente desde el formulario de contacto.</li>
            <li>Crear y mantener una cuenta cuando se solicitan las funcionalidades de acceso.</li>
            <li>Gestionar solicitudes, disponibilidad y operaciones vinculadas a reservas de herramientas.</li>
            <li>Cumplir obligaciones legales cuando resulten aplicables.</li>
          </ul>
          <p>Estos tratamientos se realizan para gestionar la solicitud o funcionalidad pedida por la persona usuaria y, cuando corresponda, para atender obligaciones legales aplicables.</p>
        </section>

        <section aria-labelledby="privacy-contact">
          <h2 id="privacy-contact">Formulario de contacto</h2>
          <p>La consulta se remite por correo electrónico al canal configurado por AUREA para poder responderla. Actualmente, el contenido del formulario no se guarda como un registro propio en la base de datos de AUREA.</p>
        </section>

        <section aria-labelledby="privacy-google">
          <h2 id="privacy-google">Inicio de sesión con Google</h2>
          <p>El acceso con Google solo se utiliza cuando la persona decide elegir esa opción. Para vincular o crear la cuenta, AUREA trata el identificador de Google, el email verificado y el nombre facilitado por ese proveedor.</p>
        </section>

        <section aria-labelledby="privacy-providers">
          <h2 id="privacy-providers">Proveedores tecnológicos</h2>
          <p>Para operar la plataforma, AUREA utiliza proveedores tecnológicos de alojamiento, base de datos, correo, autenticación e imágenes del catálogo.</p>
          <ul>
            <li>Vercel, para el alojamiento del frontend.</li>
            <li>Render, para el alojamiento del backend.</li>
            <li>Neon, para la base de datos.</li>
            <li>Resend, para el envío de mensajes del formulario de contacto.</li>
            <li>Google, cuando se utiliza el inicio de sesión con Google.</li>
            <li>Google Analytics, para la medición estadística de la web cuando se acepta la categoría de Analítica.</li>
            <li>Cloudinary, para el almacenamiento y entrega de imágenes del catálogo.</li>
          </ul>
        </section>

        <section aria-labelledby="privacy-retention">
          <h2 id="privacy-retention">Conservación</h2>
          <p>Los datos se conservarán durante el tiempo necesario para gestionar la finalidad correspondiente y, posteriormente, durante los periodos que puedan resultar exigibles por obligaciones legales.</p>
        </section>

        <section aria-labelledby="privacy-rights">
          <h2 id="privacy-rights">Tus derechos</h2>
          <p>Puedes solicitar acceso, rectificación, supresión, oposición, limitación del tratamiento y portabilidad cuando proceda. Para ello, puedes escribir a <a href={`mailto:${legalInfo.legalEmail}`}>{legalInfo.legalEmail}</a>.</p>
        </section>

        <section aria-labelledby="privacy-security">
          <h2 id="privacy-security">Seguridad</h2>
          <p>La plataforma aplica controles técnicos orientados a proteger las cuentas y las reservas, como el almacenamiento de contraseñas mediante hash, sesiones autenticadas y acceso privado a la información de cada cuenta.</p>
        </section>

        <section aria-labelledby="privacy-changes">
          <h2 id="privacy-changes">Cambios en esta política</h2>
          <p>AUREA podrá actualizar esta política cuando cambien los tratamientos realizados o las funcionalidades de la web. La versión vigente estará disponible en esta misma página.</p>
          <p>También puedes consultar la <Link href="/politica-de-cookies">Política de cookies</Link>.</p>
        </section>
      </div>
    </main>
  );
}
