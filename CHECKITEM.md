# CHECKITEM — my manual test run sheet (Postgres trial)

Only things I have to do **by hand**. The 95 automated tests already cover the logic
(rounding math, lock rules, amend flag, change-log rows, legacy restore, tax-calc plan) on SQLite —
I don't need to re-test those by clicking. What tests can NOT tell me: how it looks, how it feels in the
browser, and whether it behaves the same on Postgres with real data.

Rule for every step: **Do → Expect → write what I actually saw.** Fail = write it in Notes with the URL and the exact message.

Order matters. Do the steps top to bottom; each one prepares the next.

---

## Step 0 — Safety (do first, 10 min)

- [ ] Commit or stash the current work (`git status` is clean, or I know what is uncommitted). `db/db.sqlite3` is modified — decide if it goes in the commit.
- [ ] Create a **new empty** Postgres DB used only for this test. Never point the trial at real data.
- [ ] Enable the Postgres block in `core/settings.py`, set DB_* env vars, confirm `psycopg` is installed.
- [ ] `python manage.py migrate` → no errors (this is the first time 0036 and 0037 run on Postgres).
- [ ] `python manage.py test invoice` **against Postgres** → all pass. (Only ever run on SQLite so far.)
- [ ] Before every restore attempt: `pg_dump` the DB. The automatic pre-restore backup does **nothing** on Postgres.

**Recommended approach:** if step 0 fails, stop. Nothing below is meaningful on a broken migrate.

## Step 1 — Restore `Invoice.json` (the most important step)

Old data must still import exactly as before.

- [ ] Restore page → upload `Invoice.json` → preview shows **no conflicts**.
- [ ] Apply → counts of line items / invoices / item codes match the dump.
- [ ] Open 3–5 old invoices I know well: totals (税抜, 消費税, 税込) equal what I remember / the old PDFs.
- [ ] Tax-exempt (無税) lines are 0%, everything else 10%.
- [ ] Restore the same file again → adds nothing, changes nothing.
- [ ] Open an old invoice PDF → looks like the ones I issued before (this is the real regression check).

**Recommended approach:** compare against **old PDFs I already sent**. Numbers matching an invoice a client already holds is the only proof that counts.

## Step 2 — Line items page (`/account-items`)

Month filter here = **該当月** (work month), not the invoice date.

- [ ] Pick month + client → right rows show.
- [ ] Add a row, edit an amount, save → totals update.
- [ ] Change several rows, press save once → all saved.
- [ ] Make one row invalid (e.g. blank required field) + change another → **nothing** saved (all-or-nothing).
- [ ] Delete a row on an unsent invoice → gone.
- [ ] Stop the backend, try to save → I get a clear "not saved" message; restart backend, **reload page** → works again.

**Recommended approach:** the "screen froze" report earlier was not reproduced. Watch for it here and, if it happens, note *which action* froze and check the browser Console (F12) and the `next dev` terminal.

## Step 3 — Recalculate tax (two places)

Line items page (matches 該当月) **and** Invoices page (matches 請求日). Test both.

- [ ] Button greyed out until a month is chosen.
- [ ] A row with only 税抜 → 税 and 税込 filled.
- [ ] A row with only 税込 → 税抜 and 税 filled.
- [ ] A row where 税抜 and 税込 disagree → dialog; nothing written until I confirm; "skip" leaves it alone.
- [ ] Run it twice in a row → second run changes nothing.
- [ ] Line items page: type an edit but don't save, press Recalculate → confirm what happens to my unsaved typing (the page says "save first"; I want to see it myself).

**Recommended approach:** use a copy of a real month. Rounding is now 四捨五入 for new invoices — check a few by calculator, especially a line ending in a half-yen.

## Step 4 — Send, then amend (修正版)

Use a **test invoice**, not a restored real one.

- [ ] Invoices page → find it (filter month = **請求日**, usually one month after 該当月).
- [ ] 送信済みにする → shows 送信済み + date.
- [ ] Edit an amount on it → badge **修正版** appears on the Invoices page.
- [ ] Add a line → allowed, uses the invoice's existing date, still 修正版.
- [ ] Delete a line → stays grayed out, gone from totals.
- [ ] Try to change client or invoice date on the sent invoice → inputs are disabled.
- [ ] 未送信に戻す → client/date editable again; **修正版 stays**.
- [ ] Send again → total unchanged.
- [ ] Edit an invoice that was **never sent** → must NOT show 修正版.

**Recommended approach:** this is the flow the client-facing 修正版 PDF depends on. Do it end-to-end once, in one sitting, without shortcuts.

## Step 5 — PDF (visual — only I can judge this)

Buttons: Invoices page, in the table row and in each invoice's card below.

- [ ] Preview PDF opens in a new tab; Download saves a file.
- [ ] Amended invoice: heading **請求書（修正版）** and filename ends with `（修正版）`.
- [ ] Normal invoice: heading 請求書, no suffix.
- [ ] Header has only 請求書番号 and 発行日 (no 対象月 at the top).
- [ ] 対象月 column in the table is right on every row; an invoice with two months shows both, one per row.
- [ ] Client name: short / ~18 chars / 30+ chars / 40+ chars → shrinks, wraps, never runs into the issuer block.
- [ ] Print it (or view at 100%) — is the small font still readable?
- [ ] Long invoice (many lines) → spills to page 2 without cutting a row.
- [ ] Hanko stamp overlapping the address is **intentional** (business custom) — do not report.

**Recommended approach:** I could not view PDFs as images during development (no image renderer here) — the long-name layout was only checked by measurements. My eyes on the real PDF are the actual test. Try the longest real client name I have.

## Step 6 — Change log (audit)

There is no screen for it yet. Use `/api/v1/change-log/` in the browser (while logged in), or Django admin → ChangeLog.

- [ ] Edit a line → an entry shows old → new for only the changed fields, my username, time.
- [ ] Add / delete / void a line → entries for create / delete / void.
- [ ] Delete an unsent line → its entry is still there afterwards.
- [ ] `?item=<id>` and `?invoice=<slug>` filters work.
- [ ] Edits made *before* this feature are not in the log — expected.
- [ ] Decide: is the API/admin enough, or do I want a history panel on the line items page? (Not built.)

**Known gaps (expected, not bugs):** import "replace" mode and restore do not write log entries.

## Step 7 — Everything else

- [ ] CSV export for a date range → correct rows, voided lines excluded.
- [ ] Import (create mode): upload same file twice → no duplicates.
- [ ] Import into a period whose invoice is sent → refused with a message.
- [ ] Align invoice dates → preview, then apply; sent invoices are skipped.
- [ ] Old Django pages (`/update`, invoice detail) still load and save.
- [ ] From another device on LAN/VPN (`http://<host>:3000`): save, import, restore all work (this broke once before).

## Step 8 — Sign-off

- [ ] Every step passed, or has a written note below.
- [ ] Backup exists and I know how to roll back.
- [ ] For **every** environment (Docker, real Postgres): run `manage.py migrate` **before** the new code takes traffic. Skipping `0037_changelog` makes every save fail with a 500 — this already happened once on the dev DB.

---

## Things I might forget

1. `migrate` on each environment — not just the test one.
2. `pg_dump` before each restore (no auto-backup on Postgres).
3. The two "month" filters differ: Line items = 該当月, Invoices = 請求日.
4. Test amending on a **test** invoice; 修正版 never resets once set.
5. Look at the real PDF myself, with the longest client name.
6. Uncommitted changes and `db/db.sqlite3` — commit before switching databases.
7. Reload the page after any failed save.

## Notes / failures

| Step | What I did | What I saw | URL / message |
|------|------------|------------|---------------|
|      |            |            |               |
