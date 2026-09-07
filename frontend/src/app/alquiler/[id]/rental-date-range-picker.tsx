"use client";

import { DayPicker, type DateRange } from "react-day-picker";
import { es } from "react-day-picker/locale";
import { useEffect, useId, useRef, useState } from "react";

import styles from "./rental-date-range-picker.module.css";

type RentalDateRangePickerProps = {
  disabled?: boolean;
  endDate: string;
  minDate: string;
  onChange: (startDate: string, endDate: string) => void;
  startDate: string;
};

type ActiveField = "start" | "end";

function dateFromIso(value: string): Date | undefined {
  if (!value) {
    return undefined;
  }

  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return undefined;
  }

  return new Date(year, month - 1, day);
}

function dateToIso(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function formatDate(value: string): string {
  const date = dateFromIso(value);
  if (!date) {
    return "dd/mm/aaaa";
  }

  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

function CalendarIcon() {
  return (
    <svg aria-hidden="true" fill="none" focusable="false" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" viewBox="0 0 24 24">
      <rect height="17" rx="2.5" width="18" x="3" y="4" />
      <path d="M8 2.5v3M16 2.5v3M3 9h18" />
    </svg>
  );
}

export default function RentalDateRangePicker({
  disabled = false,
  endDate,
  minDate,
  onChange,
  startDate,
}: RentalDateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeField, setActiveField] = useState<ActiveField>("start");
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverId = useId();
  const minimumDate = dateFromIso(minDate);
  const range: DateRange | undefined = startDate
    ? { from: dateFromIso(startDate), to: dateFromIso(endDate) }
    : undefined;

  function closePicker(restoreFocus = false) {
    setIsOpen(false);
    if (restoreFocus) {
      requestAnimationFrame(() => triggerRef.current?.focus());
    }
  }

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        closePicker();
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closePicker(true);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  function openPicker(field: ActiveField, trigger: HTMLButtonElement) {
    if (disabled) {
      return;
    }

    triggerRef.current = trigger;
    setActiveField(field);
    setIsOpen(true);
  }

  function handleSelect(nextRange: DateRange | undefined, triggerDate: Date) {
    if (!nextRange?.from) {
      onChange("", "");
      return;
    }

    if (startDate && endDate) {
      onChange(dateToIso(triggerDate), "");
      setActiveField("end");
      return;
    }

    const nextStartDate = dateToIso(nextRange.from);
    const nextEndDate = nextRange.to ? dateToIso(nextRange.to) : "";
    onChange(nextStartDate, nextEndDate);

    if (nextEndDate) {
      closePicker();
    } else {
      setActiveField("end");
    }
  }

  const statusText = endDate
    ? `Rango seleccionado: del ${formatDate(startDate)} al ${formatDate(endDate)}.`
    : startDate
      ? `Inicio seleccionado: ${formatDate(startDate)}. Selecciona la fecha de devolución.`
      : "Selecciona la fecha de inicio y la fecha de devolución.";

  return (
    <div className={styles.picker} ref={rootRef}>
      <div className={styles.fields}>
        <div className={styles.field}>
          <span className={styles.label} id={`${popoverId}-start-label`}>Fecha de inicio</span>
          <button
            aria-controls={isOpen ? popoverId : undefined}
            aria-expanded={isOpen}
            aria-haspopup="dialog"
            aria-labelledby={`${popoverId}-start-label`}
            className={`${styles.dateTrigger} ${isOpen && activeField === "start" ? styles.activeTrigger : ""}`}
            disabled={disabled}
            onClick={(event) => openPicker("start", event.currentTarget)}
            type="button"
          >
            <span className={startDate ? undefined : styles.placeholder}>{formatDate(startDate)}</span>
            <CalendarIcon />
          </button>
        </div>

        <div className={styles.field}>
          <span className={styles.label} id={`${popoverId}-end-label`}>Fecha de devolución</span>
          <button
            aria-controls={isOpen ? popoverId : undefined}
            aria-expanded={isOpen}
            aria-haspopup="dialog"
            aria-labelledby={`${popoverId}-end-label`}
            className={`${styles.dateTrigger} ${isOpen && activeField === "end" ? styles.activeTrigger : ""}`}
            disabled={disabled}
            onClick={(event) => openPicker("end", event.currentTarget)}
            type="button"
          >
            <span className={endDate ? undefined : styles.placeholder}>{formatDate(endDate)}</span>
            <CalendarIcon />
          </button>
        </div>
      </div>

      {isOpen && minimumDate && (
        <div aria-label="Selecciona las fechas de alquiler" className={styles.popover} id={popoverId} role="dialog">
          <p aria-live="polite" className={styles.selectionStatus}>{statusText}</p>
          <DayPicker
            autoFocus
            classNames={{
              root: styles.calendar,
              months: styles.months,
              month: styles.month,
              month_caption: styles.monthCaption,
              caption_label: styles.captionLabel,
              nav: styles.navigation,
              button_previous: styles.navigationButton,
              button_next: styles.navigationButton,
              chevron: styles.chevron,
              month_grid: styles.monthGrid,
              weekdays: styles.weekdays,
              weekday: styles.weekday,
              weeks: styles.weeks,
              week: styles.week,
              day: styles.day,
              day_button: styles.dayButton,
              today: styles.today,
              outside: styles.outside,
              disabled: styles.disabledDay,
              range_start: styles.rangeStart,
              range_middle: styles.rangeMiddle,
              range_end: styles.rangeEnd,
            }}
            defaultMonth={range?.from ?? minimumDate}
            disabled={{ before: minimumDate }}
            locale={es}
            mode="range"
            onSelect={handleSelect}
            selected={range}
            weekStartsOn={1}
          />
          <button className={styles.closeButton} onClick={() => closePicker(true)} type="button">
            Cerrar calendario
          </button>
        </div>
      )}
    </div>
  );
}
