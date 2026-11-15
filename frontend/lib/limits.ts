// Display helpers for a link's expiry date and click limit. Whether a link still
// works is decided by the backend (link.active); these only turn values into text.
import type { Link } from "./api";

const when = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export function limitSummary(link: Link): { text: string; tone: "off" | "warn" | "plain" } | null {
  if (link.inactive_reason === "expired") return { text: "Expired", tone: "off" };
  if (link.inactive_reason === "click_limit") return { text: "Click limit reached", tone: "off" };
  const parts: string[] = [];
  if (link.max_clicks !== null) parts.push(`${link.max_clicks - link.click_count} of ${link.max_clicks} clicks left`);
  if (link.expires_at !== null) parts.push(`expires ${when.format(new Date(link.expires_at))}`);
  if (parts.length === 0) return null;
  const nearlyOut = link.max_clicks !== null && link.max_clicks - link.click_count <= Math.max(1, link.max_clicks * 0.1);
  const text = parts.join(", ");
  return { text: text[0].toUpperCase() + text.slice(1), tone: nearlyOut ? "warn" : "plain" };
}

/** <input type="datetime-local"> value (local time, no zone) -> ISO string with zone, or null. */
export function localInputToIso(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

/** ISO string -> value for <input type="datetime-local"> in the viewer's time zone. */
export function isoToLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
