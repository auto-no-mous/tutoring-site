import { apiClient } from "@/api/client";
import type { Booking, RecurringSeriesDetail } from "@/types/booking";
import type { Slot } from "@/types/tutor";

export async function createBooking(payload: {
  tutor_id: string;
  lesson_type_id: string;
  start_at: string;
  repeat_weekly: boolean;
}) {
  const { data } = await apiClient.post<Booking>("/bookings", payload);
  return data;
}

export async function listMyBookings() {
  const { data } = await apiClient.get<Booking[]>("/bookings/me");
  return data;
}

export async function cancelBooking(id: string, reason?: string) {
  const { data } = await apiClient.post<Booking>(`/bookings/${id}/cancel`, { reason: reason ?? null });
  return data;
}

export async function rescheduleBooking(id: string, newStartAt: string) {
  const { data } = await apiClient.post<Booking>(`/bookings/${id}/reschedule`, { new_start_at: newStartAt });
  return data;
}

export async function getRescheduleDates(bookingId: string, dateFrom: string, dateTo: string) {
  const { data } = await apiClient.get<string[]>(`/bookings/${bookingId}/reschedule/dates`, {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function getRescheduleSlots(bookingId: string, date: string) {
  const { data } = await apiClient.get<Slot[]>(`/bookings/${bookingId}/reschedule/slots`, { params: { date } });
  return data;
}

export async function stopSeries(seriesId: string) {
  const { data } = await apiClient.post(`/bookings/series/${seriesId}/stop`);
  return data;
}

export async function listMyRecurringSeries() {
  const { data } = await apiClient.get<RecurringSeriesDetail[]>("/bookings/series/me");
  return data;
}

export async function createManualBooking(payload: {
  student_id?: string | null;
  lesson_type_id?: string | null;
  start_at: string;
  end_at: string;
  meeting_link?: string | null;
  notes?: string | null;
  repeat_weekly?: boolean;
}) {
  const { data } = await apiClient.post<Booking>("/bookings/manual", payload);
  return data;
}

export async function listTutorBookings() {
  const { data } = await apiClient.get<Booking[]>("/bookings/tutor/me");
  return data;
}

export async function updateBooking(id: string, payload: Partial<Booking>) {
  const { data } = await apiClient.patch<Booking>(`/bookings/${id}`, payload);
  return data;
}

export async function deleteBooking(id: string) {
  await apiClient.delete(`/bookings/${id}`);
}
