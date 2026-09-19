"""
Add-only, per-organization restore from a Django `dumpdata` JSON backup (the
same format already produced by backup_logic.dump_postgres_to_json_to_nas
and by `python manage.py dumpdata`).

It only ever ADDS what the backup has and the live database doesn't. Rows
already live are left exactly as they are and nothing is updated or deleted,
so restoring an old dump can never overwrite or remove newer data - including
invoices already sent. The organization's own profile is never touched.

"Already live" is decided by what a row IS, not by its id: ids drift between a
backup and the live database (e.g. after a repair that renumbered rows), so
the same id can hold a different record on each side. Per model:

  bank account  name + branch + account number
  item code     slug
  client        slug (or name)
  line item     client, item code, invoice/action dates, name, note, amount, tax
                rate - the same key the Import screen uses to spot duplicates,
                so identical lines count as one (including repeats inside the
                backup itself, e.g. one taken before the triplication repair)
  invoice       account_item_slug (unique per client + month)

A line whose client + month already has a SENT invoice is never added (reported
as `skipped_sent`): that would change the total of a document the client holds.

A row that isn't live is created at its backup id when that id is free, and
otherwise at a new id; everything that points at it (line item -> client/item
code, invoice -> line item) follows. Invoice numbers embed the invoice's own id,
so one only changes in the rare case its id is already taken by another invoice
- that is reported as `renumbered`.

Two-step by design: `build_restore_plan` + `RestorePlan.diff()` is entirely
read-only and safe to call as often as you like; `RestorePlan.apply()` is the
only thing that writes, and it runs the exact same resolution as diff().

A backup taken before migration 0026 also predates `RenameModel(Company ->
Client)`, so its rows are still labelled `invoice.company` - `_index_by_model`
folds those into `invoice.client` so every such backup is handled exactly
like a same-name one, both here and in the legacy (pre-multitenancy) branch
of `build_restore_plan`.
"""
import json
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.core.management.color import no_style
from django.core.serializers import deserialize
from django.db import connections, transaction

from . import calc
from .models import AccountItem, BankAccount, Client, InvoiceCode, ItemCode, Organization


class RestoreError(Exception):
    pass


# Old model name -> current one, for fixtures dumped before a RenameModel
# migration. Only `Company` has ever been renamed (see 0026); add here if
# that ever happens again.
LEGACY_MODEL_ALIASES = {"invoice.company": "invoice.client"}

LEGACY_DEFAULT_SLUG = "default"


def _fields_for(row):
    return row["fields"]


def _index_by_model(fixture_rows):
    by_model = {}
    for row in fixture_rows:
        model = LEGACY_MODEL_ALIASES.get(row.get("model"), row.get("model"))
        by_model.setdefault(model, []).append(row)
    return by_model


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


class _Report:
    """Per-model outcome, keyed by the backup's own ids."""

    def __init__(self):
        self.create, self.kept, self.renumbered, self.skipped_sent, self.skipped_partial = [], [], [], [], []


@dataclass
class RestorePlan:
    organization: Organization
    backup_org_pk: int | None
    organization_row: dict | None
    bank_account_rows: list
    item_code_rows: list
    client_rows: list
    account_item_rows: list
    invoice_code_rows: list

    def conflicts(self):
        # Kept for the API shape. Ids that collide with another organization's
        # rows used to block a restore; nothing is written at a colliding id
        # any more (the row simply gets a new one), so there is nothing to block.
        return []

    def _account_item_default_tax_rate(self):
        """A backup taken before tax_rate existed (migration 0032) has no rate
        on any line; migration 0033 set 無税 (slug NT) items to 0% and left
        the rest at the 10% default - reproduce that for rows created here."""
        slug_by_pk = {r["pk"]: _fields_for(r).get("slug") for r in self.item_code_rows}
        slug_by_pk.update(ItemCode.objects.filter(organization=self.organization).values_list("pk", "slug"))
        return lambda fields: fields.get("tax_rate", 0 if slug_by_pk.get(fields.get("item_code")) == "NT" else 10)

    def _run(self, write, decisions=None):
        """
        Resolves every backup row against the live database and (if `write`)
        creates the missing ones. diff() and apply() both go through here, so
        a preview is exactly what an apply does.

        `decisions` maps a period (client slug + month, e.g. "acme-202509") to
        "add" or "skip" for periods that already have some lines live: with
        "add" the backup's missing lines are added to that (unsent) invoice,
        anything else - the default - leaves the period alone. Returns
        (reports, periods) where `periods` describes every period that needed
        a decision or was frozen because its invoice was sent.
        """
        decisions = decisions or {}
        org = self.organization
        reports = {key: _Report() for key in ("bank_account", "item_code", "client", "account_item", "invoice_code")}

        def create(Model, row, fields, report, prefer_dump_pk=True):
            taken = taken_pks[Model]
            target = row["pk"] if prefer_dump_pk and row["pk"] not in taken else None
            report.create.append(row["pk"])
            if target is None:
                report.renumbered.append(row["pk"])
            if not write:
                # A preview can't know an auto-assigned id; a placeholder that
                # can never equal a live id is enough for matching later rows.
                new_pk = target if target is not None else ("new", Model.__name__, row["pk"])
            else:
                payload = [{"model": Model._meta.label_lower, "pk": target, "fields": fields}]
                (deserialized,) = list(deserialize("json", json.dumps(payload), ignorenonexistent=True))
                deserialized.save()
                new_pk = deserialized.object.pk
            taken.add(new_pk)
            return new_pk

        taken_pks = {M: set(M.objects.values_list("pk", flat=True)) for M in (BankAccount, ItemCode, Client, AccountItem, InvoiceCode)}

        # --- bank accounts (global rows; identity = name + branch + number)
        live_bank = {(b.name, b.branch_code, b.account_number): b.pk for b in BankAccount.objects.all()}
        bank_map = {}
        for row in self.bank_account_rows:
            f = _fields_for(row)
            key = (f.get("name"), f.get("branch_code"), f.get("account_number"))
            if key in live_bank:
                bank_map[row["pk"]] = live_bank[key]
                reports["bank_account"].kept.append(row["pk"])
            else:
                bank_map[row["pk"]] = live_bank[key] = create(BankAccount, row, dict(f), reports["bank_account"])

        # --- item codes (identity = slug)
        live_codes = {i.slug: i.pk for i in ItemCode.objects.filter(organization=org)}
        item_code_map = {}
        for row in self.item_code_rows:
            f = _fields_for(row)
            if f.get("slug") in live_codes:
                item_code_map[row["pk"]] = live_codes[f["slug"]]
                reports["item_code"].kept.append(row["pk"])
            else:
                fields = {**f, "organization": org.pk}
                item_code_map[row["pk"]] = live_codes[f.get("slug")] = create(ItemCode, row, fields, reports["item_code"])

        # --- clients (identity = slug, else name)
        def client_key(f):
            return f.get("slug") or f"name:{f.get('name')}"
        live_clients = {client_key({"slug": c.slug, "name": c.name}): c.pk for c in Client.objects.filter(organization=org)}
        client_map = {}
        for row in self.client_rows:
            f = _fields_for(row)
            key = client_key(f)
            if key in live_clients:
                client_map[row["pk"]] = live_clients[key]
                reports["client"].kept.append(row["pk"])
            else:
                fields = {**f, "organization": org.pk}
                if "bank_account" in f:
                    fields["bank_account"] = bank_map.get(f["bank_account"], f["bank_account"])
                client_map[row["pk"]] = live_clients[key] = create(Client, row, fields, reports["client"])

        # --- line items (identity = what a person entered)
        default_tax_rate = self._account_item_default_tax_rate()

        # A period whose invoice has already been sent is frozen: adding a line
        # to it would change the total of a document the client already holds.
        invoices_by_period = calc.invoice_codes_by_period(org)
        client_slug = {c.pk: c.slug for c in Client.objects.filter(organization=org)}
        client_name = {c.pk: c.name for c in Client.objects.filter(organization=org)}
        for row in self.client_rows:
            live_pk = client_map.get(row["pk"])
            if live_pk is not None:
                client_slug.setdefault(live_pk, _fields_for(row).get("slug"))
                client_name.setdefault(live_pk, _fields_for(row).get("name"))

        def item_key(company, item_code, f, tax_rate):
            return (company, item_code, f.get("invoice_date"), f.get("action_date"),
                    f.get("action_name") or "", f.get("action_note") or "", f.get("invoice_bt", 0), tax_rate)

        live_items = {}
        live_period_lines = {}
        for a in AccountItem.objects.filter(organization=org).order_by("pk"):
            key = item_key(a.company_id, a.item_code_id,
                           {"invoice_date": _iso(a.invoice_date), "action_date": _iso(a.action_date),
                            "action_name": a.action_name, "action_note": a.action_note, "invoice_bt": a.invoice_bt},
                           a.tax_rate)
            live_items.setdefault(key, a.pk)
            if a.invoice_date:
                pk_ym = (a.company_id, a.invoice_date.strftime("%Y-%m"))
                live_period_lines[pk_ym] = live_period_lines.get(pk_ym, 0) + 1

        periods = {}

        def period_entry(slug, company, sent, live_lines):
            return periods.setdefault(slug, {
                "period": slug, "company_name": client_name.get(company), "sent": sent,
                "live_lines": live_lines, "lines": [], "decision": None,
            })

        item_map = {}
        left_out_keys = set()   # lines not added (period sent / not chosen): a repeat of one is the same line, not another
        for row in self.account_item_rows:
            f = _fields_for(row)
            company = client_map.get(f.get("company"), f.get("company"))
            item_code = item_code_map.get(f.get("item_code"), f.get("item_code"))
            tax_rate = default_tax_rate(f)
            key = item_key(company, item_code, f, tax_rate)
            invoice_date = f.get("invoice_date")
            ym = invoice_date[:7] if invoice_date else None
            period = f"{client_slug.get(company)}-{ym.replace('-', '')}" if ym else None
            live_lines = live_period_lines.get((company, ym), 0)
            line_info = {"invoice_date": invoice_date, "action_name": f.get("action_name") or "", "invoice_bt": f.get("invoice_bt", 0)}

            if key in live_items:
                item_map[row["pk"]] = live_items[key]
                reports["account_item"].kept.append(row["pk"])
                continue
            if key in left_out_keys:
                reports["account_item"].kept.append(row["pk"])
                continue
            live_invoice = invoices_by_period.get((company, ym))
            if live_invoice is not None and live_invoice.sent_at:
                left_out_keys.add(key)
                period_entry(period, company, True, live_lines)["lines"].append(line_info)
                reports["account_item"].skipped_sent.append(row["pk"])
                continue

            fields = {"tax_rate": tax_rate, **f, "organization": org.pk, "company": company, "item_code": item_code}
            if live_lines:
                # Some of this period is already live: only add the rest if asked to.
                entry = period_entry(period, company, False, live_lines)
                entry["lines"].append(line_info)
                entry["decision"] = "add" if decisions.get(period) == "add" else "skip"
                if entry["decision"] != "add":
                    left_out_keys.add(key)
                    reports["account_item"].skipped_partial.append(row["pk"])
                    continue
                # Join the invoice that already exists for the period, so it is counted in its total.
                fields["slug"] = live_invoice.account_item_slug if live_invoice else None
                fields["flag"] = live_invoice is not None
            item_map[row["pk"]] = live_items[key] = create(AccountItem, row, fields, reports["account_item"])

        # --- invoices (identity = account_item_slug, which is unique)
        live_slugs = set(InvoiceCode.objects.values_list("account_item_slug", flat=True))
        for row in self.invoice_code_rows:
            f = _fields_for(row)
            if f.get("account_item_slug") in live_slugs or f.get("account_item") not in item_map:
                reports["invoice_code"].kept.append(row["pk"])
                continue
            # Every invoice in a backup that predates tax_rounding was totalled
            # with 切捨て; stamp that so restoring it can't re-round its totals.
            fields = {"tax_rounding": "floor", **f, "account_item": item_map[f["account_item"]]}
            create(InvoiceCode, row, fields, reports["invoice_code"])
            live_slugs.add(f["account_item_slug"])

        if write:
            # Explicit pks were inserted directly - on backends with a real
            # sequence (Postgres) that sequence hasn't advanced, so the next
            # auto-assigned id could collide with one we just added. No-op on SQLite.
            _reset_sequences([BankAccount, ItemCode, Client, AccountItem, InvoiceCode])
        return reports, sorted(periods.values(), key=lambda p: p["period"])

    def diff(self, decisions=None):
        """Read-only summary of what apply() would do. Never writes."""
        reports, _ = self._run(write=False, decisions=decisions)
        return {
            key: {"label": f"invoice.{key.replace('_', '')}", "create": sorted(r.create), "kept": sorted(r.kept), "remapped": len(r.renumbered),
                  "skipped_sent": len(r.skipped_sent), "skipped_partial": len(r.skipped_partial)}
            for key, r in reports.items()
        }

    def periods(self, decisions=None):
        """Periods that need a decision (some lines already live) or are frozen (invoice sent)."""
        return self._run(write=False, decisions=decisions)[1]

    def apply(self, decisions=None):
        """
        Adds what's missing (see module docstring). Nothing live is changed -
        and that is checked, not assumed: every row that existed before must be
        byte-for-byte the same afterwards, otherwise the whole restore is
        rolled back (it all runs in one transaction) and nothing is written.
        """
        before = _snapshot()
        with transaction.atomic():
            reports, _ = self._run(write=True, decisions=decisions)
            after = _snapshot()
            damaged = sorted(str(k) for k, v in before.items() if after.get(k) != v)
            if damaged:
                raise RestoreError(
                    f"Safety check failed: {len(damaged)} existing row(s) would have been changed or removed "
                    f"(e.g. {damaged[:3]}). Nothing was written."
                )
        return {
            "added": {k: len(r.create) for k, r in reports.items()},
            "kept": {k: len(r.kept) for k, r in reports.items()},
            "renumbered": {k: len(r.renumbered) for k, r in reports.items()},
            "skipped_sent": {k: len(r.skipped_sent) for k, r in reports.items()},
            "skipped_partial": {k: len(r.skipped_partial) for k, r in reports.items()},
        }


def build_restore_plan(organization, fixture_rows):
    by_model = _index_by_model(fixture_rows)
    all_org_rows = by_model.get("invoice.organization", [])

    if not all_org_rows:
        # This backup predates the multi-tenancy migration (2026-09-16),
        # which retrofitted every pre-existing Client/ItemCode/AccountItem
        # row onto one backfilled Organization(slug="default") - so a
        # backup taken before that has no invoice.organization model at
        # all, and none of its rows carry an `organization` field either.
        # Everything in it belongs, unambiguously, to that one legacy org.
        if organization.slug != LEGACY_DEFAULT_SLUG:
            raise RestoreError(
                f"This backup has no organization data (it predates multi-tenancy), so it can only "
                f"be restored into the '{LEGACY_DEFAULT_SLUG}' organization, not '{organization.slug}'."
            )
        backup_org_row = None
        backup_org_pk = None
        item_code_rows = by_model.get("invoice.itemcode", [])
        client_rows = by_model.get("invoice.client", [])
        account_item_rows = by_model.get("invoice.accountitem", [])
    else:
        org_rows = [r for r in all_org_rows if _fields_for(r).get("slug") == organization.slug]
        if not org_rows:
            raise RestoreError(f"No organization with slug '{organization.slug}' found in this backup.")
        if len(org_rows) > 1:
            raise RestoreError(f"Backup contains {len(org_rows)} organizations with slug '{organization.slug}'; expected exactly one.")
        backup_org_row = org_rows[0]
        backup_org_pk = backup_org_row["pk"]
        item_code_rows = [r for r in by_model.get("invoice.itemcode", []) if _fields_for(r).get("organization") == backup_org_pk]
        client_rows = [r for r in by_model.get("invoice.client", []) if _fields_for(r).get("organization") == backup_org_pk]
        account_item_rows = [r for r in by_model.get("invoice.accountitem", []) if _fields_for(r).get("organization") == backup_org_pk]

    account_item_pks = {r["pk"] for r in account_item_rows}
    invoice_code_rows = [r for r in by_model.get("invoice.invoicecode", []) if _fields_for(r).get("account_item") in account_item_pks]

    bank_account_pks = {_fields_for(backup_org_row).get("bank_account")} if backup_org_row is not None else set()
    bank_account_pks.update(_fields_for(r).get("bank_account") for r in client_rows)
    bank_account_pks.discard(None)
    bank_account_rows = [r for r in by_model.get("invoice.bankaccount", []) if r["pk"] in bank_account_pks]

    return RestorePlan(
        organization=organization,
        backup_org_pk=backup_org_pk,
        organization_row=backup_org_row,
        bank_account_rows=bank_account_rows,
        item_code_rows=item_code_rows,
        client_rows=client_rows,
        account_item_rows=account_item_rows,
        invoice_code_rows=invoice_code_rows,
    )


def _snapshot():
    """Every row of every table a restore may touch, for before/after comparison."""
    return {
        (M.__name__, row["id"]): repr(sorted(row.items()))
        for M in (BankAccount, ItemCode, Client, AccountItem, InvoiceCode)
        for row in M.objects.values()
    }


def _zip_sqlite(db_path, dest_dir, label="pre-restore"):
    """Consistent copy of a SQLite file (via SQLite's own backup API, safe
    while the app is running) into <dest_dir>/<label>-<timestamp>.zip."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = dest_dir / f"{label}-{stamp}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        copy_path = Path(tmp) / f"db.sqlite3.{label}-{stamp}"
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        dst = sqlite3.connect(copy_path)
        with dst:
            src.backup(dst)
        src.close(); dst.close()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copy_path, copy_path.name)
    return zip_path


def backup_database_file():
    """
    Safety copy taken right before a restore is applied. Returns the zip's
    path, or None when there is no local file to copy (in-memory, or a
    server database such as Postgres - that one is covered by the existing
    NAS dump instead).
    """
    settings_db = connections["default"].settings_dict
    if settings_db["ENGINE"] != "django.db.backends.sqlite3" or str(settings_db["NAME"]) in ("", ":memory:"):
        return None
    db_path = Path(settings_db["NAME"])
    if not db_path.exists():
        return None
    return _zip_sqlite(db_path, db_path.parent / "backups")


def _reset_sequences(models):
    connection = connections["default"]
    with connection.cursor() as cursor:
        for statement in connection.ops.sequence_reset_sql(no_style(), models):
            cursor.execute(statement)
