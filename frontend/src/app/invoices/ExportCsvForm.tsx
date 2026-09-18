"use client";

import { useState } from "react";

export default function ExportCsvForm({ defaultStart, defaultEnd }: { defaultStart: string; defaultEnd: string }) {
  const [start, setStart] = useState(defaultStart);
  const [end, setEnd] = useState(defaultEnd);
  const [error, setError] = useState("");

  // The actual file transfer is a plain top-level GET submission (not
  // fetch+blob): browsers reliably turn a Content-Disposition: attachment
  // response from a real navigation into a download. Triggering it instead
  // via fetch().then(blob => link.click()) is fragile — once there's an
  // `await` between the click and the download, some browsers no longer
  // treat it as user-initiated and silently drop the download. JS here only
  // blocks the submit when the inputs are invalid.
  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    if (!start || !end) {
      e.preventDefault();
      setError("Pick both a start and end date.");
      return;
    }
    if (end < start) {
      e.preventDefault();
      setError("End date must be on or after the start date.");
      return;
    }
    setError("");
  }

  return (
    <form
      action="/export-csv"
      method="get"
      onSubmit={handleSubmit}
      className="mb-6 flex flex-wrap items-end gap-4 card p-4"
    >
      <div>
        <label className="field-label">Export CSV: from</label>
        <input
          type="date"
          name="start"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          required
          className="field-input"
        />
      </div>
      <div>
        <label className="field-label">to</label>
        <input
          type="date"
          name="end"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          required
          className="field-input"
        />
      </div>
      <button type="submit" className="btn-secondary">
        Export CSV
      </button>
      {error && <p className="w-full text-sm text-red-600">{error}</p>}
    </form>
  );
}
