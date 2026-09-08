"use client";

import { DayPicker, type DateRange, type Matcher } from "react-day-picker";
import { es } from "react-day-picker/locale";
import { useEffect, useId, useRef, useState } from "react";

import { getToolUnavailableRanges, type UnavailableDateRange } from "@/lib/api";

import styles from "./rental-date-range-picker.module.css";

type RentalDateRangePickerProps = {
  disabled?: boolean;
  endDate: string;
  minDate: string;
  onChange: (startDate: string, endDate: string) => void;
  startDate: string;
  toolId: number;
};

type ActiveField = "start" | "end";
type UnavailableMonth = {
  activeRental: boolean;
  ranges: UnavailableDateRange[];
};

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

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function getMonthPeriod(month: Date): { startDate: string; endDate: string } {
  const startDate = new Date(month.getFullYear(), month.getMonth(), 1);
  const endDate = new Date(month.getFullYear(), month.getMonth() + 1, 0);

  return { startDate: dateToIso(startDate), endDate: dateToIso(endDate) };
}

function toMatchers(ranges: UnavailableDateRange[]): Matcher[] {
  return ranges.flatMap(({ start_date, end_date }) => {
    const from = dateFromIso(start_date);
    const to = dateFromIso(end_date);

    return from && to ? [{ from, to }] : [];
  });
}

function mergeUnavailableRanges(
  existingRanges: UnavailableDateRange[],
  nextRanges: UnavailableDateRange[],
): UnavailableDateRange[] {
  const rangesByKey = new Map(
    existingRanges.map((range) => [`${range.start_date}:${range.end_date}`, range]),
  );

  for (const range of nextRanges) {
    rangesByKey.set(`${range.start_date}:${range.end_date}`, range);
  }

  return [...rangesByKey.values()];
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
  toolId,
}: RentalDateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeField, setActiveField] = useState<ActiveField>("start");
  const [displayMonth, setDisplayMonth] = useState(() => dateFromIso(startDate) ?? dateFromIso(minDate) ?? new Date());
  const [knownUnavailableRanges, setKnownUnavailableRanges] = useState<UnavailableDateRange[]>([]);
  const [hasActiveRental, setHasActiveRental] = useState(false);
  const [loadingMonthKey, setLoadingMonthKey] = useState<string | null>(null);
  const unavailableRangesByMonth = useRef(new Map<string, UnavailableMonth>());
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverId = useId();
  const minimumDate = dateFromIso(minDate);
  const range: DateRange | undefined = startDate
    ? { from: dateFromIso(startDate), to: dateFromIso(endDate) }
    : undefined;
  const currentMonthKey = monthKey(displayMonth);
  const unavailableMatchers = toMatchers(knownUnavailableRanges);

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

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const cachedMonth = unavailableRangesByMonth.current.get(currentMonthKey);
    if (cachedMonth) {
      setKnownUnavailableRanges((existingRanges) => mergeUnavailableRanges(existingRanges, cachedMonth.ranges));
      setHasActiveRental(cachedMonth.activeRental);
      setLoadingMonthKey(null);
      return;
    }

    let cancelled = false;
    const { startDate: periodStartDate, endDate: periodEndDate } = getMonthPeriod(displayMonth);
    setLoadingMonthKey(currentMonthKey);

    void getToolUnavailableRanges(toolId, periodStartDate, periodEndDate).then((result) => {
      if (result.status !== "success") {
        if (!cancelled) {
          setLoadingMonthKey(null);
        }
        return;
      }

      unavailableRangesByMonth.current.set(
        currentMonthKey,
        {
          activeRental: result.unavailableRanges.active_rental,
          ranges: result.unavailableRanges.unavailable_ranges,
        },
      );
      if (!cancelled) {
        setHasActiveRental(result.unavailableRanges.active_rental);
      }
      setKnownUnavailableRanges((existingRanges) =>
        mergeUnavailableRanges(existingRanges, result.unavailableRanges.unavailable_ranges),
      );
      if (!cancelled) {
        setLoadingMonthKey(null);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [currentMonthKey, displayMonth, isOpen, toolId]);

  function openPicker(field: ActiveField, trigger: HTMLButtonElement) {
    if (disabled) {
      return;
    }

    triggerRef.current = trigger;
    setActiveField(field);
    setDisplayMonth(range?.from ?? minimumDate ?? new Date());
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

  const statusText = loadingMonthKey === currentMonthKey
    ? "Cargando fechas no disponibles…"
    : hasActiveRental
      ? "Esta herramienta está actualmente en alquiler y no admite nuevas fechas."
    : endDate
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
            disabled={loadingMonthKey === currentMonthKey || hasActiveRental ? true : [{ before: minimumDate }, ...unavailableMatchers]}
            excludeDisabled
            locale={es}
            mode="range"
            modifiers={{ unavailable: unavailableMatchers }}
            modifiersClassNames={{ unavailable: styles.unavailableDay }}
            onSelect={handleSelect}
            onMonthChange={setDisplayMonth}
            selected={range}
            month={displayMonth}
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
