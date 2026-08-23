"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  getAccountReservation,
  type AccountReservationDetail,
} from "@/lib/api";

import styles from "./page.module.css";

type DetailState =
  | { kind: "loading" }
  | { kind: "success"; reservation: AccountReservationDetail }
  | { kind: "not-found" }
  | { kind: "error" };

const statusLabels: Record<AccountReservationDetail["status"], string> = {
  pending_review: "Pendiente de revisión",
  pending_payment: "Pendiente de pago",
  confirmed: "Confirmada",
  cancelled: "Cancelada",
  expired: "Caducada",
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "long" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("es-ES", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatAmount(value: string | null): string | null {
  return value === null
    ? null
    : new Intl.NumberFormat("es-ES", {
        style: "currency",
        currency: "EUR",
      }).format(Number(value));
}

function formatKilometres(value: string | null): string | null {
  return value === null ? null : `${value.replace(".", ",")} km`;
}

function ReservationDetail({ reservation }: { reservation: AccountReservationDetail }) {
  const expiredPayment =
    reservation.status === "pending_payment" && reservation.payment_expired;
  const statusLabel = expiredPayment ? "Caducada" : statusLabels[reservation.status];
  const statusClass = expiredPayment
    ? styles.statusExpired
    : styles[`status${reservation.status}`];
  const rentalAmount = formatAmount(reservation.rental_amount);
  const deliveryAmount = formatAmount(reservation.delivery_amount);
  const totalAmount = formatAmount(reservation.total_amount);
  const dailyPrice = formatAmount(reservation.daily_price_snapshot);
  const pricePerKm = formatAmount(reservation.delivery_price_per_km_snapshot);
  const billableKm = formatKilometres(reservation.billable_km);

  return (
    <section className={styles.detail} aria-labelledby="reservation-title">
      <Link className={styles.backLink} href="/mi-cuenta">
        <span aria-hidden="true">← </span>Volver a Mi cuenta
      </Link>

      <header className={styles.heading}>
        <div>
          <p className={styles.eyebrow}>Reserva #{reservation.id}</p>
          <h1 id="reservation-title">{reservation.tool.name}</h1>
        </div>
        <span className={`${styles.status} ${statusClass}`}>{statusLabel}</span>
      </header>

      <section className={styles.card} aria-labelledby="summary-title">
        <h2 id="summary-title">Resumen de la reserva</h2>
        <dl className={styles.details}>
          <div>
            <dt>Fechas</dt>
            <dd>
              {formatDate(reservation.start_date)} – {formatDate(reservation.end_date)}
            </dd>
          </div>
          {reservation.charged_days !== null && (
            <div>
              <dt>Duración</dt>
              <dd>
                {reservation.charged_days}{" "}
                {reservation.charged_days === 1 ? "día" : "días"}
              </dd>
            </div>
          )}
          <div>
            <dt>Modalidad</dt>
            <dd>
              {reservation.fulfillment_method === "delivery"
                ? "Transporte"
                : "Recogida en almacén"}
            </dd>
          </div>
        </dl>
      </section>

      {reservation.fulfillment_method === "delivery" && (
        <section className={styles.card} aria-labelledby="delivery-title">
          <h2 id="delivery-title">Transporte</h2>
          {reservation.delivery_address && (
            <dl className={styles.details}>
              <div className={styles.fullWidth}>
                <dt>Dirección de entrega</dt>
                <dd>{reservation.delivery_address}</dd>
              </div>
            </dl>
          )}
          {reservation.status === "pending_review" ? (
            <p className={styles.notice}>
              AUREA está valorando los kilómetros de transporte. El importe definitivo
              estará disponible después de la revisión.
            </p>
          ) : (
            <dl className={styles.details}>
              {billableKm && (
                <div>
                  <dt>Kilómetros facturables</dt>
                  <dd>{billableKm}</dd>
                </div>
              )}
              {pricePerKm && (
                <div>
                  <dt>Tarifa aplicada</dt>
                  <dd>{pricePerKm}/km</dd>
                </div>
              )}
              {deliveryAmount && (
                <div>
                  <dt>Importe de transporte</dt>
                  <dd>{deliveryAmount}</dd>
                </div>
              )}
            </dl>
          )}
        </section>
      )}

      <section className={styles.card} aria-labelledby="amounts-title">
        <h2 id="amounts-title">Resumen económico</h2>
        {reservation.status === "pending_review" ? (
          <p className={styles.notice}>
            El transporte está pendiente de valoración, por lo que todavía no hay un
            importe definitivo.
          </p>
        ) : (
          <dl className={styles.amounts}>
            {dailyPrice && (
              <div>
                <dt>Precio diario aplicado</dt>
                <dd>{dailyPrice}</dd>
              </div>
            )}
            {rentalAmount && (
              <div>
                <dt>Alquiler</dt>
                <dd>{rentalAmount}</dd>
              </div>
            )}
            <div>
              <dt>Transporte</dt>
              <dd>{deliveryAmount ?? "Sin coste"}</dd>
            </div>
            {totalAmount && (
              <div className={styles.amountTotal}>
                <dt>Total</dt>
                <dd>{totalAmount}</dd>
              </div>
            )}
          </dl>
        )}
        {reservation.status === "pending_payment" &&
          !expiredPayment &&
          reservation.payment_expires_at && (
            <p className={styles.paymentNotice}>
              Esta reserva está pendiente de pago hasta el{" "}
              {formatDateTime(reservation.payment_expires_at)}.
            </p>
          )}
        {expiredPayment && (
          <p className={styles.notice}>El plazo de pago de esta reserva ha caducado.</p>
        )}
        {reservation.status === "confirmed" && (
          <p className={styles.confirmedNotice}>Tu reserva está confirmada.</p>
        )}
      </section>

      <section className={styles.card} aria-labelledby="contact-title">
        <h2 id="contact-title">Datos de la reserva</h2>
        <p className={styles.cardIntro}>
          Estos son los datos de contacto asociados a esta reserva.
        </p>
        <dl className={styles.details}>
          <div>
            <dt>Nombre</dt>
            <dd>{reservation.customer_name}</dd>
          </div>
          <div>
            <dt>Correo electrónico</dt>
            <dd>{reservation.customer_email}</dd>
          </div>
          <div>
            <dt>Teléfono</dt>
            <dd>{reservation.customer_phone}</dd>
          </div>
        </dl>
      </section>
    </section>
  );
}

export function ReservationDetailContent() {
  const { id } = useParams<{ id: string }>();
  const reservationId = Number(id);
  const hasValidReservationId =
    Number.isSafeInteger(reservationId) && reservationId >= 1;
  const { isLoading, refreshUser, user } = useAuth();
  const router = useRouter();
  const [detailState, setDetailState] = useState<DetailState>({ kind: "loading" });

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, router, user]);

  useEffect(() => {
    if (!user || !hasValidReservationId) {
      return;
    }

    let mounted = true;
    void getAccountReservation(reservationId).then(async (result) => {
      if (!mounted) {
        return;
      }

      if (result.status === "unauthenticated") {
        await refreshUser();
        return;
      }

      if (result.status === "success") {
        setDetailState({ kind: "success", reservation: result.reservation });
        return;
      }

      setDetailState({ kind: result.status === "not_found" ? "not-found" : "error" });
    });

    return () => {
      mounted = false;
    };
  }, [hasValidReservationId, refreshUser, reservationId, user]);

  if (isLoading || !user) {
    return (
      <section className={styles.feedback} aria-live="polite">
        <p>Comprobando tu reserva…</p>
      </section>
    );
  }

  if (!hasValidReservationId) {
    return (
      <section className={styles.feedback} aria-labelledby="not-found-title">
        <h1 id="not-found-title">No hemos encontrado esta reserva</h1>
        <p>Puede que no exista o que ya no esté disponible desde tu cuenta.</p>
        <Link className={styles.backLink} href="/mi-cuenta">
          Volver a Mi cuenta
        </Link>
      </section>
    );
  }

  if (detailState.kind === "loading") {
    return (
      <section className={styles.feedback} aria-live="polite">
        <p>Comprobando tu reserva…</p>
      </section>
    );
  }

  if (detailState.kind === "not-found") {
    return (
      <section className={styles.feedback} aria-labelledby="not-found-title">
        <h1 id="not-found-title">No hemos encontrado esta reserva</h1>
        <p>Puede que no exista o que ya no esté disponible desde tu cuenta.</p>
        <Link className={styles.backLink} href="/mi-cuenta">
          Volver a Mi cuenta
        </Link>
      </section>
    );
  }

  if (detailState.kind === "error") {
    return (
      <section className={styles.feedback} role="alert">
        <h1>No podemos cargar esta reserva</h1>
        <p>Inténtalo de nuevo más tarde.</p>
        <Link className={styles.backLink} href="/mi-cuenta">
          Volver a Mi cuenta
        </Link>
      </section>
    );
  }

  return <ReservationDetail reservation={detailState.reservation} />;
}
