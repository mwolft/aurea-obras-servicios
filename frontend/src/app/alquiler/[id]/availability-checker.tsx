"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import {
  createToolReservation,
  getToolAvailability,
  type ReservationResponse,
} from "@/lib/api";

import styles from "./availability-checker.module.css";

type AvailabilityStatus =
  | { kind: "pending" }
  | { kind: "loading" }
  | { kind: "available" }
  | { kind: "unavailable" }
  | { kind: "recheck"; message: string }
  | { kind: "error"; message: string };

type ReservationStatus =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success"; reservation: ReservationResponse }
  | { kind: "error"; message: string };

type FormErrors = Partial<
  Record<"customerName" | "customerEmail" | "customerPhone" | "deliveryAddress" | "terms" | "privacy", string>
>;

type AvailabilityCheckerProps = {
  toolId: number;
  pickupAvailable: boolean;
  deliveryAvailable: boolean;
};

function getTodayIso(): string {
  const now = new Date();
  const localNow = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);

  return localNow.toISOString().slice(0, 10);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "long" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function formatExpiration(value: string): string {
  return new Intl.DateTimeFormat("es-ES", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function AvailabilityChecker({
  toolId,
  pickupAvailable,
  deliveryAvailable,
}: AvailabilityCheckerProps) {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [availabilityStatus, setAvailabilityStatus] = useState<AvailabilityStatus>({ kind: "pending" });
  const [reservationStatus, setReservationStatus] = useState<ReservationStatus>({ kind: "idle" });
  const [customerName, setCustomerName] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [fulfillmentMethod, setFulfillmentMethod] = useState<"pickup" | "delivery">(
    pickupAvailable ? "pickup" : "delivery",
  );
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const messageRef = useRef<HTMLDivElement>(null);
  const today = getTodayIso();
  const hasFulfillmentOption = pickupAvailable || deliveryAvailable;
  const isAvailable = availabilityStatus.kind === "available";

  useEffect(() => {
    if (reservationStatus.kind === "error" || reservationStatus.kind === "success") {
      messageRef.current?.focus();
    }
  }, [reservationStatus]);

  function resetAfterDateChange() {
    setAvailabilityStatus({ kind: "pending" });
    setReservationStatus({ kind: "idle" });
    setFormErrors({});
  }

  async function handleAvailabilitySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!startDate || !endDate) {
      setAvailabilityStatus({ kind: "error", message: "Selecciona la fecha de inicio y la de devolución." });
      return;
    }

    if (endDate < startDate) {
      setAvailabilityStatus({ kind: "error", message: "La devolución no puede ser anterior al inicio." });
      return;
    }

    setAvailabilityStatus({ kind: "loading" });
    setReservationStatus({ kind: "idle" });
    const result = await getToolAvailability(toolId, startDate, endDate);

    if (result.status === "success") {
      setAvailabilityStatus({ kind: result.availability.available ? "available" : "unavailable" });
      return;
    }

    if (result.status === "not_found") {
      setAvailabilityStatus({ kind: "error", message: "Esta herramienta ya no está disponible en el catálogo." });
      return;
    }

    setAvailabilityStatus({
      kind: "error",
      message: result.message ?? "No podemos consultar la disponibilidad en este momento. Inténtalo de nuevo más tarde.",
    });
  }

  function validateReservation(): FormErrors {
    const errors: FormErrors = {};

    if (!customerName.trim()) {
      errors.customerName = "Indica tu nombre.";
    }

    if (!customerEmail.trim()) {
      errors.customerEmail = "Indica tu correo electrónico.";
    } else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(customerEmail.trim())) {
      errors.customerEmail = "Indica un correo electrónico válido.";
    }

    if (!customerPhone.trim()) {
      errors.customerPhone = "Indica tu teléfono.";
    }

    if (fulfillmentMethod === "delivery" && !deliveryAddress.trim()) {
      errors.deliveryAddress = "Indica la dirección de entrega.";
    }

    if (!termsAccepted) {
      errors.terms = "Debes aceptar las condiciones de alquiler.";
    }

    if (!privacyAccepted) {
      errors.privacy = "Debes aceptar la política de privacidad.";
    }

    return errors;
  }

  async function handleReservationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!isAvailable) {
      setReservationStatus({ kind: "error", message: "Vuelve a comprobar la disponibilidad antes de enviar la solicitud." });
      return;
    }

    if (!hasFulfillmentOption) {
      setReservationStatus({ kind: "error", message: "Esta herramienta no tiene una modalidad de entrega disponible." });
      return;
    }

    const errors = validateReservation();
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) {
      setReservationStatus({ kind: "error", message: "Revisa los campos marcados antes de enviar la solicitud." });
      return;
    }

    setReservationStatus({ kind: "submitting" });
    const result = await createToolReservation(toolId, {
      start_date: startDate,
      end_date: endDate,
      customer_name: customerName.trim(),
      customer_email: customerEmail.trim(),
      customer_phone: customerPhone.trim(),
      fulfillment_method: fulfillmentMethod,
      ...(fulfillmentMethod === "delivery" ? { delivery_address: deliveryAddress.trim() } : {}),
      terms_accepted: termsAccepted,
      privacy_accepted: privacyAccepted,
    });

    if (result.status === "success") {
      setReservationStatus({ kind: "success", reservation: result.reservation });
      return;
    }

    if (result.status === "conflict") {
      setAvailabilityStatus({ kind: "recheck", message: "Las fechas ya no están disponibles. Vuelve a comprobarlas antes de reintentar." });
      setReservationStatus({ kind: "error", message: result.message });
      return;
    }

    if (result.status === "not_found") {
      setAvailabilityStatus({ kind: "error", message: "Esta herramienta ya no está disponible en el catálogo." });
      setReservationStatus({ kind: "error", message: "No podemos enviar la solicitud para esta herramienta." });
      return;
    }

    if (result.status === "validation_error") {
      setReservationStatus({ kind: "error", message: result.message });
      return;
    }

    setReservationStatus({
      kind: "error",
      message: "No podemos enviar la solicitud en este momento. Inténtalo de nuevo más tarde.",
    });
  }

  if (reservationStatus.kind === "success") {
    const { reservation } = reservationStatus;

    return (
      <section className={styles.section} tabIndex={-1} ref={messageRef}>
        {reservation.status === "pending_payment" ? (
          <>
            <h2>Reserva creada</h2>
            <p>Tu solicitud de recogida ha quedado registrada.</p>
            <dl className={styles.summary}>
              <div><dt>Fechas</dt><dd>{formatDate(reservation.start_date)} — {formatDate(reservation.end_date)}</dd></div>
              <div><dt>Días cobrados</dt><dd>{reservation.charged_days}</dd></div>
              <div><dt>Alquiler</dt><dd>{reservation.rental_amount} €</dd></div>
              <div><dt>Transporte</dt><dd>0,00 €</dd></div>
              <div><dt>Total a pagar</dt><dd>{reservation.total_amount} €</dd></div>
              <div><dt>Fianza informativa</dt><dd>{reservation.deposit_amount} €</dd></div>
            </dl>
            <p className={styles.notice}>El pago todavía no está integrado en esta fase.</p>
            {reservation.payment_expires_at && (
              <p>Esta reserva queda pendiente de pago hasta el {formatExpiration(reservation.payment_expires_at)}.</p>
            )}
          </>
        ) : (
          <>
            <h2>Solicitud de transporte recibida</h2>
            <p>Hemos registrado tu solicitud para las fechas seleccionadas.</p>
            <dl className={styles.summary}>
              <div><dt>Fechas</dt><dd>{formatDate(reservation.start_date)} — {formatDate(reservation.end_date)}</dd></div>
              <div><dt>Dirección de entrega</dt><dd>{deliveryAddress}</dd></div>
              <div><dt>Fianza informativa</dt><dd>{reservation.deposit_amount} €</dd></div>
            </dl>
            <p className={styles.notice}>AUREA revisará los kilómetros de transporte. El precio definitivo y el pago estarán disponibles después de esa revisión.</p>
          </>
        )}
      </section>
    );
  }

  return (
      <section aria-labelledby="availability-heading" className={styles.section}>
      <p className={styles.step}>Paso 1 · Elige las fechas</p>
      <h2 id="availability-heading">Consulta la disponibilidad</h2>
      <p>Selecciona las fechas para comprobar si esta herramienta puede alquilarse.</p>

      <form className={styles.form} noValidate onSubmit={handleAvailabilitySubmit}>
        <label>
          Fecha de inicio
          <input
            min={today}
            name="start_date"
            onChange={(event) => {
              setStartDate(event.target.value);
              resetAfterDateChange();
            }}
            required
            type="date"
            value={startDate}
          />
        </label>
        <label>
          Fecha de devolución
          <input
            min={startDate || today}
            name="end_date"
            onChange={(event) => {
              setEndDate(event.target.value);
              resetAfterDateChange();
            }}
            required
            type="date"
            value={endDate}
          />
        </label>
        <button disabled={availabilityStatus.kind === "loading"} type="submit">
          {availabilityStatus.kind === "loading" ? "Consultando…" : "Consultar disponibilidad"}
        </button>
      </form>

      <p className={styles.step}>Paso 2 · Comprueba la disponibilidad</p>
      <p
        aria-live="polite"
        className={
          availabilityStatus.kind === "available"
            ? styles.available
            : availabilityStatus.kind === "unavailable" || availabilityStatus.kind === "error" || availabilityStatus.kind === "recheck"
              ? styles.unavailable
              : styles.pending
        }
        role={availabilityStatus.kind === "error" || availabilityStatus.kind === "recheck" ? "alert" : undefined}
      >
        {availabilityStatus.kind === "pending" && "Selecciona las fechas de alquiler."}
        {availabilityStatus.kind === "loading" && "Consultando disponibilidad…"}
        {availabilityStatus.kind === "available" && "Disponible para las fechas seleccionadas."}
        {availabilityStatus.kind === "unavailable" && "No disponible para las fechas seleccionadas."}
        {(availabilityStatus.kind === "error" || availabilityStatus.kind === "recheck") && availabilityStatus.message}
      </p>

      {isAvailable && (
        <form className={styles.reservationForm} noValidate onSubmit={handleReservationSubmit}>
          <p className={styles.step}>Paso 3 · Completa la solicitud</p>
          <h3>Completa tu solicitud</h3>
          <p>Los importes y la disponibilidad se confirmarán siempre en el servidor.</p>

          <label>
            Nombre y apellidos
            <input aria-describedby={formErrors.customerName ? "customer-name-error" : undefined} aria-invalid={Boolean(formErrors.customerName)} onChange={(event) => setCustomerName(event.target.value)} value={customerName} />
          </label>
          {formErrors.customerName && <p className={styles.fieldError} id="customer-name-error">{formErrors.customerName}</p>}

          <label>
            Correo electrónico
            <input aria-describedby={formErrors.customerEmail ? "customer-email-error" : undefined} aria-invalid={Boolean(formErrors.customerEmail)} inputMode="email" onChange={(event) => setCustomerEmail(event.target.value)} type="email" value={customerEmail} />
          </label>
          {formErrors.customerEmail && <p className={styles.fieldError} id="customer-email-error">{formErrors.customerEmail}</p>}

          <label>
            Teléfono
            <input aria-describedby={formErrors.customerPhone ? "customer-phone-error" : undefined} aria-invalid={Boolean(formErrors.customerPhone)} onChange={(event) => setCustomerPhone(event.target.value)} type="tel" value={customerPhone} />
          </label>
          {formErrors.customerPhone && <p className={styles.fieldError} id="customer-phone-error">{formErrors.customerPhone}</p>}

          <fieldset className={styles.fulfillment}>
            <legend>Modalidad de entrega</legend>
            {pickupAvailable && (
              <label>
                <input checked={fulfillmentMethod === "pickup"} name="fulfillment_method" onChange={() => setFulfillmentMethod("pickup")} type="radio" value="pickup" />
                Recogida en almacén
              </label>
            )}
            {deliveryAvailable && (
              <label>
                <input checked={fulfillmentMethod === "delivery"} name="fulfillment_method" onChange={() => setFulfillmentMethod("delivery")} type="radio" value="delivery" />
                Transporte
              </label>
            )}
          </fieldset>

          {fulfillmentMethod === "delivery" && deliveryAvailable && (
            <>
              <label>
                Dirección de entrega
                <textarea aria-describedby={formErrors.deliveryAddress ? "delivery-address-error" : undefined} aria-invalid={Boolean(formErrors.deliveryAddress)} onChange={(event) => setDeliveryAddress(event.target.value)} value={deliveryAddress} />
              </label>
              {formErrors.deliveryAddress && <p className={styles.fieldError} id="delivery-address-error">{formErrors.deliveryAddress}</p>}
            </>
          )}

          {!hasFulfillmentOption && <p className={styles.fieldError} role="alert">Esta herramienta no tiene una modalidad de entrega disponible.</p>}

          <label className={styles.checkbox}>
            <input checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} type="checkbox" />
            Acepto las condiciones de alquiler.
          </label>
          {formErrors.terms && <p className={styles.fieldError}>{formErrors.terms}</p>}

          <label className={styles.checkbox}>
            <input checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} type="checkbox" />
            Acepto la política de privacidad.
          </label>
          {formErrors.privacy && <p className={styles.fieldError}>{formErrors.privacy}</p>}

          {reservationStatus.kind === "error" && (
            <div aria-live="assertive" className={styles.formError} ref={messageRef} role="alert" tabIndex={-1}>
              {reservationStatus.message}
            </div>
          )}

          <button disabled={reservationStatus.kind === "submitting" || !hasFulfillmentOption} type="submit">
            {reservationStatus.kind === "submitting" ? "Enviando solicitud…" : "Enviar solicitud de reserva"}
          </button>
        </form>
      )}
    </section>
  );
}
