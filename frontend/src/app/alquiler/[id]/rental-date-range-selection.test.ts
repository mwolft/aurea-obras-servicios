import { describe, expect, it } from "vitest";

import { selectRentalDate } from "./rental-date-range-selection";

describe("rental date range selection", () => {
  it("keeps the selected start date when the customer then selects a return date", () => {
    const start = selectRentalDate(
      { startDate: "", endDate: "", activeField: "start" },
      "2026-09-25",
    );
    const range = selectRentalDate(start, "2026-09-26");

    expect(range).toEqual({
      startDate: "2026-09-25",
      endDate: "2026-09-26",
      activeField: "end",
    });
  });

  it("changes only the return date when that field is active", () => {
    const selection = selectRentalDate(
      { startDate: "2026-09-25", endDate: "2026-09-26", activeField: "end" },
      "2026-09-28",
    );

    expect(selection).toMatchObject({
      startDate: "2026-09-25",
      endDate: "2026-09-28",
    });
  });

  it("changes only the start date when that field is active", () => {
    const selection = selectRentalDate(
      { startDate: "2026-09-25", endDate: "2026-09-28", activeField: "start" },
      "2026-09-26",
    );

    expect(selection).toEqual({
      startDate: "2026-09-26",
      endDate: "2026-09-28",
      activeField: "end",
    });
  });

  it("allows a same-day return when the rental rules permit it", () => {
    const selection = selectRentalDate(
      { startDate: "2026-09-25", endDate: "", activeField: "end" },
      "2026-09-25",
    );

    expect(selection).toMatchObject({
      startDate: "2026-09-25",
      endDate: "2026-09-25",
    });
  });

  it("does not alter either field when the clicked date is unavailable", () => {
    const current = { startDate: "2026-09-25", endDate: "", activeField: "end" } as const;

    expect(selectRentalDate(current, "2026-09-26", true)).toBe(current);
  });

  it("does not turn an earlier return date into a new start date", () => {
    const current = { startDate: "2026-09-25", endDate: "", activeField: "end" } as const;

    expect(selectRentalDate(current, "2026-09-24")).toBe(current);
  });
});
