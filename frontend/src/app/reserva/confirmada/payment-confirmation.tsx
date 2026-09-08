"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import Swal from "sweetalert2";
import { useEffect, useRef, useState } from "react";

import {
  capturePayPalOrder,
  getPayPalOrderStatus,
  getStripeCheckoutStatus,
  type PaymentReturnReservation,
  type StripeCheckoutStatus,
} from "@/lib/api";

import {
  getPaymentReturnOutcome,
  getPaymentReturnReference,
  reservePaymentSuccessAlert,
} from "./payment-return-state";
import styles from "./page.module.css";

const POLL_INTERVAL_MS = 1_500;
const MAX_POLL_ATTEMPTS = 10;

type ReturnState =
  | { kind: "loading" }
  | { kind: "waiting"; reservation: PaymentReturnReservation }
  | { kind: "confirmed"; reservation: PaymentReturnReservation }
  | { kind: "requires_review"; reservation: PaymentReturnReservation }
  | { kind: "expired"; reservation: PaymentReturnReservation }
  | { kind: "not_found" }
  | { kind: "error" };

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "long" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function formatAmount(value: string | null): string {
  if (value === null) {
    return "No disponible";
  }

  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
  }).format(Number(value));
}

function pause(): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
}

function clearReturnParameters() {
  window.history.replaceState(null, "", "/reserva/confirmada");
}

export function PaymentConfirmation() {
  const searchParams = useSearchParams();
  const { provider, externalPaymentId } = getPaymentReturnReference(searchParams);
  const [state, setState] = useState<ReturnState>(() => (
    provider && externalPaymentId ? { kind: "loading" } : { kind: "not_found" }
  ));
  const alertShown = useRef(false);

  useEffect(() => {
    if (!provider || !externalPaymentId) {
      return;
    }

    let active = true;

    async function loadPaymentReturn() {
      // PayPal's browser return asks AUREA to capture its Order, but that call
      // never confirms the reservation. The verified webhook remains the only
      // authority for the following polling result.
      if (provider === "paypal") {
        await capturePayPalOrder(externalPaymentId!);
        if (!active) return;
      }

      for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
        let payment: StripeCheckoutStatus | null = null;
        let resultStatus: "success" | "not_found" | "error" = "error";

        if (provider === "stripe") {
          const result = await getStripeCheckoutStatus(externalPaymentId!);
          resultStatus = result.status;
          if (result.status === "success") {
            payment = result.checkout;
          }
        } else {
          const result = await getPayPalOrderStatus(externalPaymentId!);
          resultStatus = result.status;
          if (result.status === "success") {
            payment = result.order;
          }
        }

        if (!active) return;

        if (resultStatus === "not_found") {
          clearReturnParameters();
          setState({ kind: "not_found" });
          return;
        }

        if (resultStatus !== "success" || payment === null) {
          if (attempt < MAX_POLL_ATTEMPTS - 1) {
            await pause();
            continue;
          }
          setState({ kind: "error" });
          return;
        }

        const outcome = getPaymentReturnOutcome(payment);
        if (outcome === "confirmed") {
          clearReturnParameters();
          setState({ kind: "confirmed", reservation: payment.reservation });
          return;
        }

        if (outcome === "requires_review") {
          clearReturnParameters();
          setState({ kind: "requires_review", reservation: payment.reservation });
          return;
        }

        if (outcome === "expired") {
          clearReturnParameters();
          setState({ kind: "expired", reservation: payment.reservation });
          return;
        }

        setState({ kind: "waiting", reservation: payment.reservation });
        if (attempt < MAX_POLL_ATTEMPTS - 1) {
          await pause();
        }
      }
    }

    void loadPaymentReturn();
    return () => {
      active = false;
    };
  }, [provider, externalPaymentId]);

  useEffect(() => {
    if (state.kind !== "confirmed" || alertShown.current) {
      return;
    }

    const storageKey = `aurea:payment-confirmed:${provider}:${externalPaymentId}`;
    if (!reservePaymentSuccessAlert(window.sessionStorage, storageKey)) {
      return;
    }

    alertShown.current = true;
    void Swal.fire({
      icon: "success",
      title: "¡Pago realizado!",
      text: "Tu reserva ha quedado confirmada correctamente.",
      confirmButtonText: "Ver resumen",
      buttonsStyling: false,
      customClass: {
        popup: styles.alertPopup,
        title: styles.alertTitle,
        htmlContainer: styles.alertContent,
        confirmButton: styles.alertButton,
        icon: styles.alertIcon,
      },
    });
  }, [externalPaymentId, provider, state]);

  if (state.kind === "loading") {
    return <StatusCard title="Estamos confirmando tu pago…" text="Estamos consultando el estado seguro de tu reserva." />;
  }

  if (state.kind === "not_found") {
    return <StatusCard title="No encontramos esta reserva" text="Vuelve a tu cuenta o contacta con AUREA si necesitas ayuda." />;
  }

  if (state.kind === "error") {
    return <StatusCard title="No hemos podido comprobar el pago" text="Actualiza la página dentro de unos instantes o consulta tu reserva desde Mi cuenta." />;
  }

  if (state.kind === "requires_review") {
    return <ReservationSummary reservation={state.reservation} title="Estamos revisando la reserva" notice="Hemos recibido el pago y estamos revisando la reserva." />;
  }

  if (state.kind === "expired") {
    return <ReservationSummary reservation={state.reservation} title="La reserva no se ha confirmado" notice="La ventana de pago ha caducado. Si necesitas ayuda, contacta con AUREA." />;
  }

  if (state.kind === "waiting") {
    return <ReservationSummary reservation={state.reservation} title="Estamos confirmando tu pago…" notice="Estamos esperando la confirmación segura del proveedor de pago. Este proceso puede tardar unos instantes." />;
  }

  return <ReservationSummary paymentConfirmed reservation={state.reservation} title="Reserva confirmada" />;
}

function StatusCard({ title, text }: { title: string; text: string }) {
  return (
    <section aria-live="polite" className={styles.card}>
      <p className={styles.eyebrow}>AUREA · ALQUILER</p>
      <h1>{title}</h1>
      <p className={styles.intro}>{text}</p>
      <div className={styles.actions}>
        <Link className={styles.primaryAction} href="/mi-cuenta">Ver mi reserva</Link>
        <Link className={styles.secondaryAction} href="/">Volver al inicio</Link>
      </div>
    </section>
  );
}

function ReservationSummary({
  reservation,
  title,
  notice,
  paymentConfirmed = false,
}: {
  reservation: PaymentReturnReservation;
  title: string;
  notice?: string;
  paymentConfirmed?: boolean;
}) {
  return (
    <section aria-live="polite" className={styles.card}>
      <p className={styles.eyebrow}>AUREA · ALQUILER</p>
      <h1>{title}</h1>
      {notice && <p className={styles.notice}>{notice}</p>}
      <p className={styles.reference}>Referencia de reserva #{reservation.id}</p>

      <dl className={styles.summary}>
        <div>
          <dt>Herramienta</dt>
          <dd>{reservation.tool.name}</dd>
        </div>
        <div>
          <dt>Fechas</dt>
          <dd>{formatDate(reservation.start_date)} — {formatDate(reservation.end_date)}</dd>
        </div>
        <div>
          <dt>Modalidad</dt>
          <dd>{reservation.fulfillment_method === "delivery" ? "Entrega" : "Recogida"}</dd>
        </div>
        {reservation.fulfillment_method === "delivery" && reservation.delivery_address && (
          <div className={styles.fullWidth}>
            <dt>Dirección de entrega</dt>
            <dd>{reservation.delivery_address}</dd>
          </div>
        )}
        <div>
          <dt>{paymentConfirmed ? "Importe pagado" : "Importe de la reserva"}</dt>
          <dd>{formatAmount(reservation.total_amount)}</dd>
        </div>
        <div>
          <dt>Fianza</dt>
          <dd>{formatAmount(reservation.deposit_amount)}</dd>
        </div>
      </dl>

      <div className={styles.actions}>
        <Link className={styles.primaryAction} href={`/mi-cuenta/reservas/${reservation.id}`}>Ver mi reserva</Link>
        <Link className={styles.secondaryAction} href="/">Volver al inicio</Link>
      </div>
    </section>
  );
}
