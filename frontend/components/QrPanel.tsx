"use client";
import { useEffect, useState } from "react";
import { api, ApiError, type Link } from "@/lib/api";

/** Shows the link's QR code and offers SVG / PNG downloads. Scans go through the short URL, so they're counted. */
export default function QrPanel({ link }: { link: Link }) {
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    api.qrCode(link.id, "svg")
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setPreview(url);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load the QR code."));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [link.id]);

  async function download(format: "svg" | "png") {
    try {
      const url = URL.createObjectURL(await api.qrCode(link.id, format));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${link.code}-qr.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't download the QR code.");
    }
  }

  return (
    <section className="panel qr-panel" aria-labelledby="qr-title">
      <div className="qr-text">
        <h2 id="qr-title">QR code</h2>
        <p className="muted">Print it or add it to a poster. Scans open {link.short_url} and count as clicks.</p>
        <div className="qr-actions">
          <button type="button" className="btn-quiet" onClick={() => download("png")}>Download PNG</button>
          <button type="button" className="btn-quiet" onClick={() => download("svg")}>Download SVG</button>
        </div>
        {error && <p role="alert" className="error">{error}</p>}
      </div>
      {preview && <img className="qr-image" src={preview} alt={`QR code for ${link.short_url}`} width={128} height={128} />}
    </section>
  );
}
