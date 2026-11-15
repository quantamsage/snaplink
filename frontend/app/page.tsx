"use client";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import CopyButton from "@/components/CopyButton";
import { api, ApiError, type Link as ShortLink } from "@/lib/api";
import { limitSummary, localInputToIso } from "@/lib/limits";
import { useRequireAuth } from "@/lib/useRequireAuth";

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
}

export default function Dashboard() {
  const ready = useRequireAuth();
  const [links, setLinks] = useState<ShortLink[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [url, setUrl] = useState("");
  const [customCode, setCustomCode] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [maxClicks, setMaxClicks] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [justCreated, setJustCreated] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setLoadError(null);
      setLinks((await api.listLinks()).items);
    } catch (err) {
      setLoadError(message(err));
    }
  }, []);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      const link = await api.createLink(url.trim(), customCode.trim() || null, {
        expires_at: localInputToIso(expiresAt),
        max_clicks: maxClicks ? Number(maxClicks) : null,
      });
      setUrl("");
      setCustomCode("");
      setExpiresAt("");
      setMaxClicks("");
      setJustCreated(link.id);
      await load();
    } catch (err) {
      setFormError(message(err));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(link: ShortLink) {
    if (!window.confirm(`Delete /r/${link.code}? Its click history is deleted too.`)) return;
    try {
      await api.deleteLink(link.id);
      await load();
    } catch (err) {
      setLoadError(message(err));
    }
  }

  if (!ready) return null;

  return (
    <main className="page">
      <section className="create">
        <h1>Shorten a link</h1>
        <form onSubmit={onCreate} className="create-form">
          <label className="grow">
            Long URL
            <input
              type="url"
              required
              placeholder="https://example.com/a/very/long/page"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <label>
            <span>Custom code <span className="optional">(optional)</span></span>
            <input
              type="text"
              placeholder="spring-sale"
              pattern="[A-Za-z0-9_\-]{3,32}"
              title="3–32 letters, numbers, - or _"
              value={customCode}
              onChange={(e) => setCustomCode(e.target.value)}
            />
          </label>
          <button type="submit" className="btn" disabled={busy}>
            {busy ? "Shortening…" : "Shorten"}
          </button>
          <details className="limits" open={Boolean(expiresAt || maxClicks)}>
            <summary>Limits (optional)</summary>
            <div className="limits-fields">
              <label>
                Stop working after
                <input type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
              </label>
              <label>
                Max clicks
                <input type="number" min={1} max={1000000} inputMode="numeric" placeholder="No limit"
                  value={maxClicks} onChange={(e) => setMaxClicks(e.target.value)} />
              </label>
            </div>
          </details>
        </form>
        {formError && <p role="alert" className="error">{formError}</p>}
      </section>

      <section aria-labelledby="your-links">
        <h2 id="your-links">Your links</h2>
        {loadError && (
          <p role="alert" className="error">
            {loadError} <button type="button" className="btn-quiet" onClick={load}>Retry</button>
          </p>
        )}
        {links === null && !loadError && <p className="muted">Loading your links…</p>}
        {links?.length === 0 && <p className="muted">No links yet. Paste a long URL above to make your first one.</p>}
        {links && links.length > 0 && (
          <ul className="links">
            {links.map((link) => {
              const summary = limitSummary(link);
              const classes = ["link-row", link.id === justCreated && "is-new", !link.active && "is-off"];
              return (
              <li key={link.id} className={classes.filter(Boolean).join(" ")}>
                <div className="link-main">
                  <a className="code" href={link.short_url} target="_blank" rel="noopener noreferrer">
                    /r/{link.code}
                  </a>
                  <span className="target" title={link.target_url}>{link.target_url}</span>
                  {summary && <span className={`limit limit-${summary.tone}`}>{summary.text}</span>}
                </div>
                <div className="tally" aria-label={`${link.click_count} clicks`}>
                  <span className="tally-n">{link.click_count}</span>
                  <span className="tally-label">{link.click_count === 1 ? "click" : "clicks"}</span>
                </div>
                <div className="row-actions">
                  <CopyButton text={link.short_url} />
                  <Link href={`/links/${link.id}`} className="btn-quiet">Stats</Link>
                  <button type="button" className="btn-quiet danger" onClick={() => onDelete(link)}>Delete</button>
                </div>
              </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
