export function formatTime(value: number | null | undefined): string {
  return value ? new Date(value).toLocaleString() : "Unavailable";
}

export function shortId(value: string | null | undefined, keep = 18): string {
  if (!value) return "Unavailable";
  return value.length > keep ? `${value.slice(0, keep)}…` : value;
}
