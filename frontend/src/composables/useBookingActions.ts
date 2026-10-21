import { ref, type Ref } from "vue";

import { cancelBooking, deleteBooking, updateBooking } from "@/api/bookings";
import { useToastStore } from "@/stores/toast";
import type { Booking } from "@/types/booking";

export function bookingDurationMinutes(booking: Booking): number {
  return Math.round((new Date(booking.end_at).getTime() - new Date(booking.start_at).getTime()) / 60000);
}

/**
 * Действия с занятием - общие для карточки в списке (BookingCard) и окна занятия в
 * недельном виде (BookingDetailsModal), чтобы отмена, ссылка и длительность вели себя
 * одинаково, где бы репетитор их ни нажал. onChanged - перезагрузить данные у
 * родителя; true из действия - оно выполнено.
 */
export function useBookingActions(booking: Ref<Booking>, onChanged: () => void) {
  const toast = useToastStore();
  const isBusy = ref(false);

  async function run(action: () => Promise<unknown>): Promise<boolean> {
    isBusy.value = true;
    try {
      await action();
      onChanged();
      return true;
    } finally {
      isBusy.value = false;
    }
  }

  async function cancel(): Promise<boolean> {
    if (!window.confirm("Отменить это занятие?")) return false;
    try {
      await run(() => cancelBooking(booking.value.id));
      toast.show("Занятие отменено");
      return true;
    } catch {
      toast.show("Не удалось отменить занятие");
      return false;
    }
  }

  async function removeBlock(): Promise<boolean> {
    if (!window.confirm("Удалить эту запись?")) return false;
    return run(() => deleteBooking(booking.value.id));
  }

  function saveMeetingLink(link: string, applyToStudent: boolean): Promise<boolean> {
    return run(() => updateBooking(booking.value.id, { meeting_link: link, apply_link_to_student: applyToStudent }));
  }

  function saveDuration(minutes: number): Promise<boolean> {
    const end = new Date(new Date(booking.value.start_at).getTime() + minutes * 60000);
    return run(() => updateBooking(booking.value.id, { end_at: end.toISOString() }));
  }

  return { isBusy, cancel, removeBlock, saveMeetingLink, saveDuration };
}
