"use client";
import { FormEvent, useState } from "react";
import { api, ApiError, type Link } from "@/lib/api";
import { isoToLocalInput, limitSummary, localInputToIso } from "@/lib/limits";

/** Edit or remove a link's expiry date and click limit. */
export default function LinkLimitsPanel({ link, onSaved }: { link: Link; onSaved: (l: Link) => void }) {
  const [expiresAt, setExpiresAt] = useState(isoToLocalInput(link.expires_at));
  const [maxClicks, setMaxClicks] = useState(link.max_clicks?.toString() ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const summary = limitSummary(link);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await api.updateLimits(link.id, {
        expires_at: localInputToIso(expiresAt),
        max_clicks: maxClicks ? Number(maxClicks) : null,
      });
      onSaved(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save the limits. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="limits-title">
      <h2 id="limits-title">Limits</h2>
      <p className={link.active ? "muted" : "status-off"}>
        {summary ? summary.text : "No limits. This link works until you delete it."}
        {!link.active && " Visitors see a “link no longer available” page. Raise or remove the limit to turn it back on."}
      </p>
      <form className="limits-fields" onSubmit={save}>
        <label>
          Stop working after
          <input type="datetime-local" value={expiresAt} onChange={(e) => { setExpiresAt(e.target.value); setSaved(false); }} />
        </label>
        <label>
          Max clicks
          <input type="number" min={1} max={1000000} inputMode="numeric" placeholder="No limit"
            value={maxClicks} onChange={(e) => { setMaxClicks(e.target.value); setSaved(false); }} />
        </label>
        <button type="submit" className="btn" disabled={busy}>{busy ? "Saving…" : "Save limits"}</button>
      </form>
      <p className="hint">Leave a box empty to remove that limit.</p>
      {saved && <p role="status" className="saved">Limits saved.</p>}
      {error && <p role="alert" className="error">{error}</p>}
    </section>
  );
}
