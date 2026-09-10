export interface WeekdayEntry {
  day_of_week: number;
  name: string;
}

export function getWeekdayNames(locale: string): WeekdayEntry[] {
  if (locale === "ar") {
    return [
      { day_of_week: 6, name: "السبت" },
      { day_of_week: 0, name: "الأحد" },
      { day_of_week: 1, name: "الإثنين" },
      { day_of_week: 2, name: "الثلاثاء" },
      { day_of_week: 3, name: "الأربعاء" },
      { day_of_week: 4, name: "الخميس" },
      { day_of_week: 5, name: "الجمعة" },
    ];
  }
  if (locale === "fa") {
    return [
      { day_of_week: 6, name: "شنبه" },
      { day_of_week: 0, name: "یکشنبه" },
      { day_of_week: 1, name: "دوشنبه" },
      { day_of_week: 2, name: "سه‌شنبه" },
      { day_of_week: 3, name: "چهارشنبه" },
      { day_of_week: 4, name: "پنجشنبه" },
      { day_of_week: 5, name: "جمعه" },
    ];
  }
  return [
    { day_of_week: 0, name: "Sunday" },
    { day_of_week: 1, name: "Monday" },
    { day_of_week: 2, name: "Tuesday" },
    { day_of_week: 3, name: "Wednesday" },
    { day_of_week: 4, name: "Thursday" },
    { day_of_week: 5, name: "Friday" },
    { day_of_week: 6, name: "Saturday" },
  ];
}
