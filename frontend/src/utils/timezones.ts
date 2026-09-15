// Список часовых поясов для настроек. Раньше поле было свободным текстом, и в базе
// оседали значения вроде "Chelyabinsk": посчитать по ним разницу с Москвой нельзя, а
// именно ради разницы пояс и хранится (время на сайте всегда московское).
//
// Список короткий намеренно: это Россия и соседи, откуда реально занимаются. Если у
// человека уже записан другой пояс (или браузер сообщает четвёртый), он добавляется в
// начало списка - см. timezoneOptions ниже.
export const COMMON_TIMEZONES: { value: string; label: string }[] = [
  { value: "Europe/Kaliningrad", label: "Калининград (МСК−1)" },
  { value: "Europe/Moscow", label: "Москва (МСК)" },
  { value: "Europe/Samara", label: "Самара (МСК+1)" },
  { value: "Asia/Yekaterinburg", label: "Екатеринбург, Челябинск, Пермь, Уфа (МСК+2)" },
  { value: "Asia/Omsk", label: "Омск (МСК+3)" },
  { value: "Asia/Krasnoyarsk", label: "Красноярск, Новокузнецк (МСК+4)" },
  { value: "Asia/Novosibirsk", label: "Новосибирск, Кемерово (МСК+4)" },
  { value: "Asia/Irkutsk", label: "Иркутск, Улан-Удэ (МСК+5)" },
  { value: "Asia/Yakutsk", label: "Якутск, Чита (МСК+6)" },
  { value: "Asia/Vladivostok", label: "Владивосток, Хабаровск (МСК+7)" },
  { value: "Asia/Magadan", label: "Магадан, Сахалин (МСК+8)" },
  { value: "Asia/Kamchatka", label: "Камчатка, Чукотка (МСК+9)" },
  { value: "Europe/Minsk", label: "Минск (МСК)" },
  { value: "Europe/Kyiv", label: "Киев (МСК−1)" },
  { value: "Asia/Almaty", label: "Алматы, Астана (МСК+2)" },
  { value: "Asia/Tashkent", label: "Ташкент (МСК+2)" },
  { value: "Asia/Tbilisi", label: "Тбилиси (МСК+1)" },
  { value: "Asia/Yerevan", label: "Ереван (МСК+1)" },
  { value: "Asia/Baku", label: "Баку (МСК+1)" },
];

/** Список для выпадающего списка: известные пояса плюс тот, что уже стоит у человека. */
export function timezoneOptions(current: string | null | undefined): { value: string; label: string }[] {
  const known = COMMON_TIMEZONES.some((tz) => tz.value === current);
  if (!current || known) return COMMON_TIMEZONES;
  return [{ value: current, label: current }, ...COMMON_TIMEZONES];
}

/** Пояс браузера, если он есть в списке, иначе московский. */
export function detectTimezone(): string {
  const browser = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return COMMON_TIMEZONES.some((tz) => tz.value === browser) ? browser : "Europe/Moscow";
}
