"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { sendContactMessage, type ContactMessageRequest } from "@/lib/api";

import styles from "./page.module.css";

type FormStatus = "idle" | "submitting" | "success" | "error";
type FieldName = "name" | "email" | "phone" | "subject" | "message" | "privacyAccepted";
type FieldErrors = Partial<Record<FieldName, string>>;

type ContactFormValues = ContactMessageRequest;

const initialValues: ContactFormValues = {
  name: "",
  email: "",
  phone: "",
  subject: "",
  message: "",
  privacyAccepted: false,
  website: "",
};

function validate(values: ContactFormValues): FieldErrors {
  const errors: FieldErrors = {};
  const name = values.name.trim();
  const email = values.email.trim();
  const phone = values.phone.trim();
  const subject = values.subject.trim();
  const message = values.message.trim();

  if (name.length < 2) {
    errors.name = "Indica tu nombre (al menos 2 caracteres).";
  } else if (name.length > 120) {
    errors.name = "El nombre no puede superar 120 caracteres.";
  }

  if (!email) {
    errors.email = "Indica tu email.";
  } else if (email.length > 254 || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    errors.email = "Indica un email válido.";
  }

  if (phone.length > 50) {
    errors.phone = "El teléfono no puede superar 50 caracteres.";
  }

  if (subject.length > 160) {
    errors.subject = "El asunto no puede superar 160 caracteres.";
  }

  if (message.length < 10) {
    errors.message = "El mensaje debe tener al menos 10 caracteres.";
  } else if (message.length > 5000) {
    errors.message = "El mensaje no puede superar 5000 caracteres.";
  }

  if (!values.privacyAccepted) {
    errors.privacyAccepted = "Debes aceptar el tratamiento de tus datos para enviar la consulta.";
  }

  return errors;
}

export function ContactForm() {
  const [values, setValues] = useState<ContactFormValues>(initialValues);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [status, setStatus] = useState<FormStatus>("idle");
  const statusRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (status === "success" || status === "error") {
      statusRef.current?.focus();
    }
  }, [status]);

  const updateValue = <Key extends keyof ContactFormValues>(key: Key, value: ContactFormValues[Key]) => {
    setValues((currentValues) => ({ ...currentValues, [key]: value }));
    setErrors({});
    if (status !== "idle") {
      setStatus("idle");
    }
  };

  const describedBy = (field: FieldName) => (errors[field] ? `${field}-error` : undefined);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fieldErrors = validate(values);
    setErrors(fieldErrors);

    if (Object.keys(fieldErrors).length > 0) {
      setStatus("idle");
      return;
    }

    setStatus("submitting");
    const result = await sendContactMessage({
      ...values,
      name: values.name.trim(),
      email: values.email.trim(),
      phone: values.phone.trim(),
      subject: values.subject.trim(),
      message: values.message.trim(),
    });

    if (result.status === "success") {
      setValues(initialValues);
      setErrors({});
      setStatus("success");
      return;
    }

    setStatus("error");
  };

  return (
    <form className={styles.form} noValidate onSubmit={handleSubmit}>
      <div aria-hidden="true" className={styles.honeypot}>
        <label htmlFor="website">Sitio web</label>
        <input
          autoComplete="off"
          id="website"
          name="website"
          onChange={(event) => updateValue("website", event.target.value)}
          tabIndex={-1}
          type="text"
          value={values.website}
        />
      </div>

      <div className={styles.fieldGrid}>
        <div className={styles.field}>
          <label htmlFor="contact-name">
            Nombre
            <input
              aria-describedby={describedBy("name")}
              aria-invalid={Boolean(errors.name)}
              autoComplete="name"
              id="contact-name"
              name="name"
              onChange={(event) => updateValue("name", event.target.value)}
              required
              type="text"
              value={values.name}
            />
          </label>
          {errors.name ? <p className={styles.fieldError} id="name-error">{errors.name}</p> : null}
        </div>

        <div className={styles.field}>
          <label htmlFor="contact-email">
            Email
            <input
              aria-describedby={describedBy("email")}
              aria-invalid={Boolean(errors.email)}
              autoComplete="email"
              id="contact-email"
              name="email"
              onChange={(event) => updateValue("email", event.target.value)}
              required
              type="email"
              value={values.email}
            />
          </label>
          {errors.email ? <p className={styles.fieldError} id="email-error">{errors.email}</p> : null}
        </div>

        <div className={styles.field}>
          <label htmlFor="contact-phone">
            Teléfono <span className={styles.optional}>(opcional)</span>
            <input
              aria-describedby={describedBy("phone")}
              aria-invalid={Boolean(errors.phone)}
              autoComplete="tel"
              id="contact-phone"
              name="phone"
              onChange={(event) => updateValue("phone", event.target.value)}
              type="tel"
              value={values.phone}
            />
          </label>
          {errors.phone ? <p className={styles.fieldError} id="phone-error">{errors.phone}</p> : null}
        </div>

        <div className={styles.field}>
          <label htmlFor="contact-subject">
            Asunto <span className={styles.optional}>(opcional)</span>
            <input
              aria-describedby={describedBy("subject")}
              aria-invalid={Boolean(errors.subject)}
              id="contact-subject"
              name="subject"
              onChange={(event) => updateValue("subject", event.target.value)}
              type="text"
              value={values.subject}
            />
          </label>
          {errors.subject ? <p className={styles.fieldError} id="subject-error">{errors.subject}</p> : null}
        </div>
      </div>

      <label htmlFor="contact-message">
        Mensaje
        <textarea
          aria-describedby={describedBy("message")}
          aria-invalid={Boolean(errors.message)}
          id="contact-message"
          name="message"
          onChange={(event) => updateValue("message", event.target.value)}
          required
          rows={6}
          value={values.message}
        />
      </label>
      {errors.message ? <p className={styles.fieldError} id="message-error">{errors.message}</p> : null}

      <label className={styles.privacy} htmlFor="contact-privacy">
        <input
          aria-describedby={describedBy("privacyAccepted")}
          aria-invalid={Boolean(errors.privacyAccepted)}
          checked={values.privacyAccepted}
          id="contact-privacy"
          name="privacyAccepted"
          onChange={(event) => updateValue("privacyAccepted", event.target.checked)}
          required
          type="checkbox"
        />
        <span>He leído y acepto el tratamiento de los datos enviados para responder a mi consulta.</span>
      </label>
      {errors.privacyAccepted ? (
        <p className={styles.fieldError} id="privacyAccepted-error">{errors.privacyAccepted}</p>
      ) : null}

      <div className={styles.formFooter}>
        {status === "success" ? (
          <p className={styles.successMessage} ref={statusRef} role="status" tabIndex={-1}>
            Mensaje enviado correctamente. Gracias por contactar con AUREA.
          </p>
        ) : null}
        {status === "error" ? (
          <p className={styles.errorMessage} ref={statusRef} role="alert" tabIndex={-1}>
            No hemos podido enviar el mensaje. Inténtalo de nuevo.
          </p>
        ) : null}
        <button disabled={status === "submitting"} type="submit">
          {status === "submitting" ? "Enviando…" : "Enviar consulta"}
        </button>
      </div>
    </form>
  );
}
