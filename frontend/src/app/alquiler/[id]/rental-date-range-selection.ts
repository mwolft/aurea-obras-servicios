export type RentalDateField = "start" | "end";

export type RentalDateRangeSelection = {
  startDate: string;
  endDate: string;
  activeField: RentalDateField;
};

/**
 * Applies a calendar click to the field the customer explicitly opened.
 *
 * DayPicker's range mode is used only to render the range. It must not decide
 * whether a click replaces the start or the end date: that decision belongs to
 * the active field in AUREA's two-field rental form.
 */
export function selectRentalDate(
  selection: RentalDateRangeSelection,
  selectedDate: string,
  isUnavailable = false,
): RentalDateRangeSelection {
  if (isUnavailable) {
    return selection;
  }

  if (selection.activeField === "start" || !selection.startDate) {
    return {
      startDate: selectedDate,
      endDate: selection.endDate && selection.endDate >= selectedDate ? selection.endDate : "",
      activeField: "end",
    };
  }

  // An invalid return date must not silently swap the two fields. The customer
  // keeps the chosen start date and can pick a valid return date next.
  if (selectedDate < selection.startDate) {
    return selection;
  }

  return {
    startDate: selection.startDate,
    endDate: selectedDate,
    activeField: "end",
  };
}
