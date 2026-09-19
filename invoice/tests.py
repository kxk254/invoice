import datetime

from django.test import TestCase
from django.utils import timezone

from . import calc
from .models import AccountItem, BankAccount, Client, InvoiceCode, ItemCode, Organization

MONTH = "2025-09-01"


class TaxHelperTests(TestCase):
    def test_exclusive_drops_fraction(self):
        self.assertEqual(calc.tax_on_exclusive(1005, 10), 100)
        self.assertEqual(calc.tax_on_exclusive(1019, 8), 81)

    def test_negative_mirrors_positive(self):
        # A credit line must be the exact negative of the charge it offsets.
        self.assertEqual(calc.tax_on_exclusive(-1005, 10), -100)
        self.assertEqual(calc.tax_in_inclusive(-1105, 10), -calc.tax_in_inclusive(1105, 10))

    def test_inclusive(self):
        self.assertEqual(calc.tax_in_inclusive(1100, 10), 100)
        self.assertEqual(calc.tax_in_inclusive(1080, 8), 80)

    def test_zero_rate(self):
        self.assertEqual(calc.tax_on_exclusive(5000, 0), 0)
        self.assertEqual(calc.tax_in_inclusive(5000, 0), 0)

    def test_matches_exact_math_over_a_range(self):
        for rate in (8, 10):
            for n in range(1, 20001):
                self.assertEqual(calc.tax_on_exclusive(n, rate), n * rate // 100)
                self.assertEqual(calc.tax_in_inclusive(n, rate), n * rate // (100 + rate))


class TaxCalcTestBase(TestCase):
    def setUp(self):
        bank = BankAccount.objects.create(name="Bank")
        self.org = Organization.objects.create(name="Org", slug="org", bank_account=bank)
        self.client_a = Client.objects.create(organization=self.org, name="Acme", short_name="acme", slug="acme", bank_account=bank)
        self.item_code = ItemCode.objects.create(organization=self.org, name="Fee", short_name="fee", slug="C01")

    def item(self, bt=0, at=0, tax=0, rate=10, date="2025-09-01", **extra):
        return AccountItem.objects.create(
            organization=self.org, company=self.client_a, item_code=self.item_code,
            invoice_date=datetime.date.fromisoformat(date), action_date=datetime.date.fromisoformat(date),
            invoice_bt=bt, invoice_at=at, invoice_tax=tax, tax_rate=rate, **extra,
        )

    def reload(self, obj):
        obj.refresh_from_db()
        return obj

    def make_sent_invoice(self):
        calc.set_invoice_code(self.org)
        invoice = InvoiceCode.objects.get(account_item_slug="acme-202509")
        invoice.sent_at = timezone.now()
        invoice.save()
        return invoice


class PlanTaxCalcTests(TaxCalcTestBase):
    def test_fill_from_exclusive(self):
        self.item(bt=1005)
        fills, conflicts = calc.plan_tax_calc(self.org, "", MONTH)
        self.assertEqual(conflicts, [])
        self.assertEqual(fills[0]["after"], {"bt": 1005, "tax": 100, "at": 1105})

    def test_fill_from_inclusive(self):
        self.item(at=1100)
        fills, _ = calc.plan_tax_calc(self.org, "", MONTH)
        self.assertEqual(fills[0]["after"], {"bt": 1000, "tax": 100, "at": 1100})

    def test_negative_amounts_are_filled(self):
        self.item(bt=-1005)
        self.item(at=-1100)
        fills, conflicts = calc.plan_tax_calc(self.org, "", MONTH)
        self.assertEqual(conflicts, [])
        self.assertEqual(sorted(f["after"]["tax"] for f in fills), [-100, -100])

    def test_consistent_row_is_left_alone(self):
        self.item(bt=1000, tax=100, at=1100)
        self.assertEqual(calc.plan_tax_calc(self.org, "", MONTH), ([], []))

    def test_consistent_row_with_missing_tax_only_syncs_tax(self):
        self.item(bt=1000, at=1100, tax=0)
        fills, conflicts = calc.plan_tax_calc(self.org, "", MONTH)
        self.assertEqual(conflicts, [])
        self.assertEqual(fills[0]["after"]["tax"], 100)

    def test_disagreeing_amounts_are_a_conflict(self):
        self.item(bt=1000, tax=100, at=1500)
        fills, conflicts = calc.plan_tax_calc(self.org, "", MONTH)
        self.assertEqual(fills, [])
        self.assertEqual(conflicts[0]["if_bt"], {"bt": 1000, "tax": 100, "at": 1100})
        self.assertEqual(conflicts[0]["if_at"], {"bt": 1364, "tax": 136, "at": 1500})

    def test_deleted_and_out_of_month_rows_ignored(self):
        self.item(bt=1000, deleted_at=timezone.now())
        self.item(bt=1000, date="2025-10-01")
        self.assertEqual(calc.plan_tax_calc(self.org, "", MONTH), ([], []))


class ApplyTaxCalcTests(TaxCalcTestBase):
    def test_fills_apply_and_conflict_without_choice_is_untouched(self):
        filled = self.item(bt=1000)
        conflicted = self.item(bt=1000, tax=100, at=1500)
        result = calc.apply_tax_calc(self.org, "", MONTH)
        self.assertEqual(result, {"applied": 1, "unresolved": 1, "amended_invoices": 0})
        self.assertEqual(self.reload(filled).invoice_at, 1100)
        self.assertEqual(self.reload(conflicted).invoice_at, 1500)

    def test_resolution_keep_exclusive(self):
        row = self.item(bt=1000, tax=100, at=1500)
        calc.apply_tax_calc(self.org, "", MONTH, {row.id: "bt"})
        row = self.reload(row)
        self.assertEqual((row.invoice_bt, row.invoice_tax, row.invoice_at), (1000, 100, 1100))

    def test_resolution_keep_inclusive_accepts_string_ids(self):
        row = self.item(bt=1000, tax=100, at=1500)
        calc.apply_tax_calc(self.org, "", MONTH, {str(row.id): "at"})
        row = self.reload(row)
        self.assertEqual((row.invoice_bt, row.invoice_tax, row.invoice_at), (1364, 136, 1500))

    def test_stale_resolution_for_a_consistent_row_is_ignored(self):
        row = self.item(bt=1000, tax=100, at=1100)
        result = calc.apply_tax_calc(self.org, "", MONTH, {row.id: "at"})
        self.assertEqual(result["applied"], 0)

    def test_editing_a_sent_invoice_marks_it_amended(self):
        row = self.item(bt=1000)
        invoice = self.make_sent_invoice()
        result = calc.apply_tax_calc(self.org, "", MONTH)
        self.assertEqual(result["amended_invoices"], 1)
        self.assertTrue(self.reload(invoice).amended)
        self.assertEqual(self.reload(row).invoice_at, 1100)

    def test_unsent_invoice_is_not_marked_amended(self):
        self.item(bt=1000)
        calc.set_invoice_code(self.org)
        calc.apply_tax_calc(self.org, "", MONTH)
        self.assertFalse(InvoiceCode.objects.get(account_item_slug="acme-202509").amended)

    def test_sent_invoice_with_nothing_to_change_is_not_amended(self):
        self.item(bt=1000, tax=100, at=1100)
        invoice = self.make_sent_invoice()
        calc.apply_tax_calc(self.org, "", MONTH)
        self.assertFalse(self.reload(invoice).amended)


class InvoiceTotalsTests(TaxCalcTestBase):
    def totals(self):
        calc.set_invoice_code(self.org)
        calc.total_amount_calc(self.org)
        return InvoiceCode.objects.get(account_item_slug="acme-202509")

    def test_tax_rounded_once_per_rate_not_per_line(self):
        # Three lines of 15: per line 1.5 each. Summed base 45 -> 4.5 -> one
        # rounding of the total (四捨五入 -> 5), not three roundings of 1.5.
        for _ in range(3):
            self.item(bt=15, rate=10)
        invoice = self.totals()
        self.assertEqual(invoice.invoice_tax_ttl, 5)
        self.assertEqual(invoice.invoice_at_gttl, 50)

    def test_credit_line_nets_against_charges(self):
        self.item(bt=10000)
        self.item(bt=-2500)
        invoice = self.totals()
        self.assertEqual(invoice.invoice_bt_ttl, 7500)
        self.assertEqual(invoice.invoice_tax_ttl, 750)

    def test_positive_total_rounds_half_up(self):
        self.item(bt=1005)
        self.assertEqual(self.totals().invoice_tax_ttl, 101)

    def test_negative_total_rounds_half_away_from_zero(self):
        self.item(bt=-1005)
        self.assertEqual(self.totals().invoice_tax_ttl, -101)


class TaxRoundingMethodTests(TaxCalcTestBase):
    def test_round_helper(self):
        self.assertEqual(calc.tax_on_exclusive(1005, 10, "round"), 101)   # 100.5 -> 101
        self.assertEqual(calc.tax_on_exclusive(1004, 10, "round"), 100)   # 100.4 -> 100
        self.assertEqual(calc.tax_on_exclusive(-1005, 10, "round"), -101)
        self.assertEqual(calc.tax_on_exclusive(-1004, 10, "round"), -100)
        self.assertEqual(calc.tax_on_exclusive(1005, 10), 100)            # per-line stays 切捨て

    def totals(self):
        calc.set_invoice_code(self.org)
        calc.total_amount_calc(self.org)
        return InvoiceCode.objects.get(account_item_slug="acme-202509")

    def test_draft_uses_round(self):
        self.item(bt=1005)
        invoice = self.totals()
        self.assertEqual(calc.invoice_tax_method(invoice), "round")
        self.assertEqual(invoice.invoice_tax_ttl, 101)

    def test_legacy_sent_invoice_stays_floor_and_unchanged(self):
        self.item(bt=1005)
        calc.set_invoice_code(self.org)
        invoice = InvoiceCode.objects.get(account_item_slug="acme-202509")
        InvoiceCode.objects.filter(pk=invoice.pk).update(sent_at=timezone.now(), tax_rounding="")
        calc.total_amount_calc(self.org)
        invoice = self.reload(invoice)
        self.assertEqual(calc.invoice_tax_method(invoice), "floor")
        self.assertEqual(invoice.invoice_tax_ttl, 100)

    def test_stamped_method_survives_a_change_of_default(self):
        self.item(bt=1005)
        calc.set_invoice_code(self.org)
        invoice = InvoiceCode.objects.get(account_item_slug="acme-202509")
        invoice.tax_rounding = calc.invoice_tax_method(invoice)   # what mark-sent does
        invoice.sent_at = timezone.now()
        invoice.save()
        old = calc.DEFAULT_TAX_ROUNDING
        calc.DEFAULT_TAX_ROUNDING = "floor"
        try:
            calc.total_amount_calc(self.org)
        finally:
            calc.DEFAULT_TAX_ROUNDING = old
        self.assertEqual(self.reload(invoice).invoice_tax_ttl, 101)

    def test_amended_sent_invoice_keeps_its_method(self):
        self.item(bt=1005)
        calc.set_invoice_code(self.org)
        invoice = InvoiceCode.objects.get(account_item_slug="acme-202509")
        InvoiceCode.objects.filter(pk=invoice.pk).update(sent_at=timezone.now(), tax_rounding="floor")
        self.item(bt=10)   # a correction line added after sending
        calc.set_invoice_code(self.org)
        calc.total_amount_calc(self.org)
        # base 1015 -> 101.5, floor keeps it 101 (round would give 102)
        self.assertEqual(self.reload(invoice).invoice_tax_ttl, 101)

    def test_pdf_breakdown_uses_the_invoices_method(self):
        self.item(bt=1005)
        calc.set_invoice_code(self.org)
        calc.invoice_code_slug_save(self.org)
        calc.total_amount_calc(self.org)
        ctx = calc.prepare_invoice_items(self.org, {"slug": "acme-202509"})
        self.assertEqual(ctx["tax_breakdown_rows"][0]["tax"], 101)
        InvoiceCode.objects.update(sent_at=timezone.now(), tax_rounding="floor")
        ctx = calc.prepare_invoice_items(self.org, {"slug": "acme-202509"})
        self.assertEqual(ctx["tax_breakdown_rows"][0]["tax"], 100)


import json
from pathlib import Path

from . import restore_logic

LEGACY_DUMP = Path(__file__).resolve().parent.parent / "Invoice.json"


class LegacyDumpRestoreTests(TestCase):
    """
    Restoring a dump taken before multi-tenancy (invoice.company, no tax_rate,
    no tax_rounding / sent_at / amended / deleted_at) must reproduce the
    original data - amounts and invoice totals - exactly.
    """

    @classmethod
    def setUpTestData(cls):
        if not LEGACY_DUMP.exists():
            return
        cls.rows = json.loads(LEGACY_DUMP.read_text(encoding="utf-8"))

    def setUp(self):
        if not LEGACY_DUMP.exists():
            self.skipTest("Invoice.json legacy dump not present")
        self.org, _ = Organization.objects.get_or_create(slug=restore_logic.LEGACY_DEFAULT_SLUG, defaults={"name": "Default"})

    def restore(self):
        plan = restore_logic.build_restore_plan(self.org, self.rows)
        self.assertEqual(plan.conflicts(), [])
        return plan.apply()

    def test_restores_everything_in_the_dump(self):
        result = self.restore()
        expected = {m: sum(1 for r in self.rows if r["model"] == m) for m in ("invoice.accountitem", "invoice.invoicecode", "invoice.itemcode")}
        self.assertEqual(result["added"]["account_item"], expected["invoice.accountitem"])
        self.assertEqual(result["added"]["invoice_code"], expected["invoice.invoicecode"])
        self.assertEqual(result["added"]["item_code"], expected["invoice.itemcode"])
        self.assertEqual(result["kept"]["account_item"], 0)
        self.assertEqual(Client.objects.filter(organization=self.org).count(), sum(1 for r in self.rows if r["model"] == "invoice.company"))

    def test_tax_exempt_items_do_not_become_10_percent(self):
        self.restore()
        exempt = AccountItem.objects.filter(item_code__slug="NT")
        self.assertTrue(exempt.exists())
        self.assertFalse(exempt.exclude(tax_rate=0).exists())
        self.assertFalse(AccountItem.objects.exclude(item_code__slug="NT").exclude(tax_rate=10).exists())

    def test_old_invoices_are_stamped_with_the_method_they_were_made_with(self):
        self.restore()
        self.assertFalse(InvoiceCode.objects.exclude(tax_rounding="floor").exists())

    def test_recomputed_totals_match_the_dump(self):
        self.restore()
        stored = {r["pk"]: r["fields"] for r in self.rows if r["model"] == "invoice.invoicecode"}
        calc.total_amount_calc(self.org)
        mismatches = []
        for invoice in InvoiceCode.objects.all():
            f = stored[invoice.pk]
            got = (invoice.invoice_bt_ttl_0, invoice.invoice_bt_ttl, invoice.invoice_tax_ttl, invoice.invoice_at_gttl)
            want = (f["invoice_bt_ttl_0"], f["invoice_bt_ttl"], f["invoice_tax_ttl"], f["invoice_at_gttl"])
            if got != want:
                mismatches.append((invoice.account_item_slug, got, want))
        self.assertEqual(mismatches, [])

    def test_restore_twice_is_idempotent(self):
        self.restore()
        first = AccountItem.objects.count()
        self.restore()
        self.assertEqual(AccountItem.objects.count(), first)

    def test_second_restore_adds_nothing_and_changes_nothing(self):
        self.restore()
        first = AccountItem.objects.count()
        result = self.restore()
        self.assertEqual(AccountItem.objects.count(), first)
        self.assertEqual(sum(result["added"].values()), 0)
        self.assertEqual(result["kept"]["account_item"], first)

    def test_existing_rows_are_never_overwritten(self):
        self.restore()
        item = AccountItem.objects.filter(item_code__slug="C01").first()
        invoice = InvoiceCode.objects.first()
        now = timezone.now()
        AccountItem.objects.filter(pk=item.pk).update(deleted_at=now, tax_rate=8, invoice_bt=12345, action_name="edited")
        InvoiceCode.objects.filter(pk=invoice.pk).update(sent_at=now, amended=True, tax_rounding="round", invoice_bt_ttl=999)
        self.restore()
        item, invoice = self.reload(item), self.reload(invoice)
        self.assertEqual((item.tax_rate, item.invoice_bt, item.action_name), (8, 12345, "edited"))
        self.assertIsNotNone(item.deleted_at)
        self.assertEqual((invoice.amended, invoice.tax_rounding, invoice.invoice_bt_ttl), (True, "round", 999))
        self.assertIsNotNone(invoice.sent_at)

    def test_rows_newer_than_the_dump_are_never_deleted(self):
        self.restore()
        client = Client.objects.first()
        newer = AccountItem.objects.create(
            organization=self.org, company=client, item_code=ItemCode.objects.first(),
            invoice_date=datetime.date(2030, 1, 1), action_date=datetime.date(2030, 1, 1), invoice_bt=100,
        )
        calc.set_invoice_code(self.org)
        newer_invoice = InvoiceCode.objects.get(account_item_slug=f"{client.slug}-203001")
        result = self.restore()
        self.assertTrue(AccountItem.objects.filter(pk=newer.pk).exists())
        self.assertTrue(InvoiceCode.objects.filter(pk=newer_invoice.pk).exists())
        self.assertNotIn("deleted", result)

    def test_only_rows_missing_from_the_database_are_added(self):
        self.restore()
        gone = AccountItem.objects.order_by("pk").first()
        gone_pk = gone.pk
        InvoiceCode.objects.filter(account_item=gone).delete()
        gone.delete()
        result = self.restore()
        self.assertEqual(result["added"]["account_item"], 1)
        self.assertTrue(AccountItem.objects.filter(pk=gone_pk).exists())

    def test_diff_matches_apply(self):
        plan = restore_logic.build_restore_plan(self.org, self.rows)
        diff = plan.diff()
        result = plan.apply()
        for key in ("item_code", "client", "account_item", "invoice_code"):
            self.assertEqual(len(diff[key]["create"]), result["added"][key], key)
            self.assertEqual(len(diff[key]["kept"]), result["kept"][key], key)

    def test_invoice_with_an_existing_slug_under_another_id_is_not_duplicated(self):
        self.restore()
        invoice = InvoiceCode.objects.order_by("pk").first()
        stored = InvoiceCode.objects.count()
        # Same period, but the dump's copy carries an id that isn't live.
        rows = [dict(r) for r in self.rows]
        for r in rows:
            if r["model"] == "invoice.invoicecode" and r["pk"] == invoice.pk:
                r["pk"] = 999999
        plan = restore_logic.build_restore_plan(self.org, rows)
        plan.apply()
        self.assertEqual(InvoiceCode.objects.count(), stored)

    def reload(self, obj):
        obj.refresh_from_db()
        return obj

class CurrentFormatRoundTripTests(TaxCalcTestBase):
    def test_dump_and_restore_keeps_new_fields(self):
        from django.core import serializers

        self.item(bt=1005, rate=8)
        gone = self.item(bt=500, deleted_at=timezone.now())
        calc.set_invoice_code(self.org)
        InvoiceCode.objects.update(sent_at=timezone.now(), amended=True, tax_rounding="round")
        models = [BankAccount, Organization, ItemCode, Client, AccountItem, InvoiceCode]
        rows = json.loads(serializers.serialize("json", [o for M in models for o in M.objects.all()]))

        plan = restore_logic.build_restore_plan(self.org, rows)
        self.assertEqual(plan.conflicts(), [])
        plan.apply()

        invoice = InvoiceCode.objects.get()
        self.assertTrue(invoice.amended)
        self.assertEqual(invoice.tax_rounding, "round")
        self.assertIsNotNone(invoice.sent_at)
        self.assertIsNotNone(self.reload(gone).deleted_at)
        self.assertEqual(AccountItem.objects.get(invoice_bt=1005).tax_rate, 8)


class RestoreIdCollisionTests(TaxCalcTestBase):
    """The same id can hold a different record in the backup and the live DB
    (ids get renumbered by repairs). Matching by id would attach backup
    invoices to the wrong live line items."""

    def backup_rows(self, item_pk, invoice_pk=500, bt=5000):
        return [
            {"model": "invoice.organization", "pk": 50, "fields": {"slug": "org", "name": "Org"}},
            {"model": "invoice.itemcode", "pk": 9, "fields": {"organization": 50, "slug": "C01", "name": "Fee", "short_name": "fee"}},
            {"model": "invoice.client", "pk": 7, "fields": {"organization": 50, "slug": "acme", "name": "Acme", "short_name": "acme", "bank_account": 1}},
            {"model": "invoice.accountitem", "pk": item_pk, "fields": {
                "organization": 50, "company": 7, "item_code": 9, "invoice_date": "2024-03-01", "action_date": "2024-03-01",
                "action_name": "x", "action_note": "", "invoice_bt": bt, "invoice_tax": 0, "invoice_at": 0, "slug": "acme-202403", "flag": True}},
            {"model": "invoice.invoicecode", "pk": invoice_pk, "fields": {
                "account_item": item_pk, "account_item_slug": "acme-202403", "invoice_slug": f"acme-202403-{invoice_pk:07d}",
                "invoice_bt_ttl": bt}},
        ]

    def test_backup_row_on_an_id_used_by_a_different_live_row_is_added_at_a_new_id(self):
        live = self.item(bt=1000, date="2025-09-01")
        rows = self.backup_rows(item_pk=live.pk)
        plan = restore_logic.build_restore_plan(self.org, rows)
        preview = plan.diff()
        self.assertEqual(preview["account_item"]["remapped"], 1)
        result = plan.apply()

        self.assertEqual(result["added"]["account_item"], 1)
        self.assertEqual(result["renumbered"]["account_item"], 1)
        live.refresh_from_db()
        self.assertEqual((live.invoice_bt, live.invoice_date), (1000, datetime.date(2025, 9, 1)))   # untouched
        added = AccountItem.objects.get(invoice_bt=5000)
        self.assertNotEqual(added.pk, live.pk)
        invoice = InvoiceCode.objects.get(account_item_slug="acme-202403")
        self.assertEqual(invoice.account_item_id, added.pk)          # follows the new id, not the live row at the old one
        self.assertEqual(invoice.pk, 500)                              # invoice keeps its id, so its number is unchanged
        calc.total_amount_calc(self.org)
        self.assertEqual(self.reload(invoice).invoice_bt_ttl, 5000)

    def test_same_content_at_a_different_id_is_recognised_as_present(self):
        live = self.item(bt=5000, date="2024-03-01", action_name="x")
        rows = self.backup_rows(item_pk=live.pk + 100)
        before = AccountItem.objects.count()
        result = restore_logic.build_restore_plan(self.org, rows).apply()
        self.assertEqual(AccountItem.objects.count(), before)
        self.assertEqual(result["kept"]["account_item"], 1)
        self.assertEqual(InvoiceCode.objects.get(account_item_slug="acme-202403").account_item_id, live.pk)

    def test_identical_lines_count_as_one_including_repeats_inside_the_backup(self):
        # Same rule as the Import screen; also stops a pre-repair backup that
        # holds each line three times from re-triplicating the data.
        rows = self.backup_rows(item_pk=201)
        rows.insert(4, {**rows[3], "pk": 202})
        rows.insert(4, {**rows[3], "pk": 203})
        result = restore_logic.build_restore_plan(self.org, rows).apply()
        self.assertEqual(result["added"]["account_item"], 1)
        self.assertEqual(result["kept"]["account_item"], 2)
        self.assertEqual(AccountItem.objects.filter(invoice_bt=5000).count(), 1)

    def test_invoice_id_taken_by_another_invoice_is_renumbered_and_reported(self):
        self.item(bt=1000, date="2025-09-01")
        calc.set_invoice_code(self.org)
        taken = InvoiceCode.objects.get().pk
        rows = self.backup_rows(item_pk=300, invoice_pk=taken)
        result = restore_logic.build_restore_plan(self.org, rows).apply()
        self.assertEqual(result["renumbered"]["invoice_code"], 1)
        self.assertEqual(InvoiceCode.objects.count(), 2)


class RestoreSafetyNetTests(TaxCalcTestBase):
    def test_restore_is_rolled_back_if_an_existing_row_would_change(self):
        from unittest import mock

        live = self.item(bt=1000, date="2025-09-01")
        rows = RestoreIdCollisionTests.backup_rows(self, item_pk=live.pk + 50)
        plan = restore_logic.build_restore_plan(self.org, rows)
        real_run = plan._run

        def sabotaged(write, decisions=None):
            reports = real_run(write, decisions)
            AccountItem.objects.filter(pk=live.pk).update(invoice_bt=1)   # a bug that touches live data
            return reports

        with mock.patch.object(plan, "_run", side_effect=sabotaged):
            with self.assertRaises(restore_logic.RestoreError):
                plan.apply()
        live.refresh_from_db()
        self.assertEqual(live.invoice_bt, 1000)                                  # rolled back
        self.assertFalse(AccountItem.objects.filter(invoice_bt=5000).exists())   # nothing was added either

    def test_zip_backup_contains_a_readable_copy(self):
        import sqlite3, tempfile, zipfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "live.sqlite3"
            con = sqlite3.connect(src); con.execute("create table t(x)"); con.execute("insert into t values (42)"); con.commit(); con.close()
            zip_path = restore_logic._zip_sqlite(src, Path(tmp) / "backups")
            with zipfile.ZipFile(zip_path) as z:
                (name,) = z.namelist()
                z.extract(name, tmp)
            self.assertEqual(sqlite3.connect(Path(tmp) / name).execute("select x from t").fetchone(), (42,))

    def test_no_zip_for_in_memory_test_database(self):
        self.assertIsNone(restore_logic.backup_database_file())


class RestoreSentInvoiceTests(TaxCalcTestBase):
    def test_restore_never_adds_lines_to_an_already_sent_invoice(self):
        self.item(bt=1000, date="2024-03-01", action_name="kept")
        calc.set_invoice_code(self.org)
        calc.total_amount_calc(self.org)
        InvoiceCode.objects.update(sent_at=timezone.now(), tax_rounding="floor")
        invoice = InvoiceCode.objects.get()
        totals_before = (invoice.invoice_bt_ttl, invoice.invoice_tax_ttl, invoice.invoice_at_gttl)

        # A backup whose March-2024 period carries one more line than live has.
        rows = RestoreIdCollisionTests.backup_rows(self, item_pk=900, bt=5000)
        rows = [r for r in rows if r["model"] != "invoice.invoicecode"]
        plan = restore_logic.build_restore_plan(self.org, rows)
        result = plan.apply()

        self.assertEqual(AccountItem.objects.count(), 1)
        self.assertEqual(result["added"]["account_item"], 0)
        self.assertEqual(result["skipped_sent"]["account_item"], 1)
        calc.total_amount_calc(self.org)
        invoice.refresh_from_db()
        self.assertEqual((invoice.invoice_bt_ttl, invoice.invoice_tax_ttl, invoice.invoice_at_gttl), totals_before)


class RestorePartialPeriodTests(TaxCalcTestBase):
    """A period that is already partly live is only topped up when asked to."""

    def setUp(self):
        super().setUp()
        self.live = self.item(bt=1000, date="2024-03-01", action_name="already here")
        calc.set_invoice_code(self.org)
        calc.total_amount_calc(self.org)
        # Backup's March 2024 has that line plus one more.
        rows = RestoreIdCollisionTests.backup_rows(self, item_pk=900, bt=5000)
        self.rows = [r for r in rows if r["model"] != "invoice.invoicecode"]
        self.rows.insert(4, {**self.rows[3], "pk": 901, "fields": {**self.rows[3]["fields"], "action_name": "already here", "invoice_bt": 1000}})

    def plan(self):
        return restore_logic.build_restore_plan(self.org, self.rows)

    def test_default_is_to_leave_the_period_alone(self):
        result = self.plan().apply()
        self.assertEqual(AccountItem.objects.count(), 1)
        self.assertEqual(result["skipped_partial"]["account_item"], 1)

    def test_preview_lists_the_period_with_what_would_be_added(self):
        (period,) = self.plan().periods()
        self.assertEqual(period["period"], "acme-202403")
        self.assertEqual((period["sent"], period["live_lines"], period["decision"]), (False, 1, "skip"))
        self.assertEqual([l["invoice_bt"] for l in period["lines"]], [5000])

    def test_add_decision_tops_up_the_existing_invoice_and_counts_in_its_total(self):
        result = self.plan().apply({"acme-202403": "add"})
        self.assertEqual(result["added"]["account_item"], 1)
        self.assertEqual(AccountItem.objects.count(), 2)
        invoice = InvoiceCode.objects.get(account_item_slug="acme-202403")
        calc.total_amount_calc(self.org)
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_bt_ttl, 6000)                       # 1000 live + 5000 added
        self.assertEqual(AccountItem.objects.get(invoice_bt=5000).slug, "acme-202403")

    def test_add_decision_never_overrides_a_sent_invoice(self):
        InvoiceCode.objects.update(sent_at=timezone.now(), tax_rounding="floor")
        result = self.plan().apply({"acme-202403": "add"})
        self.assertEqual(AccountItem.objects.count(), 1)
        self.assertEqual(result["skipped_sent"]["account_item"], 1)
        (period,) = self.plan().periods({"acme-202403": "add"})
        self.assertTrue(period["sent"])

    def test_decision_for_another_period_changes_nothing(self):
        self.plan().apply({"acme-209912": "add"})
        self.assertEqual(AccountItem.objects.count(), 1)

    def test_api_passes_decisions_through(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from .models import OrganizationMembership

        user = get_user_model().objects.create_user("u", password="x")
        OrganizationMembership.objects.create(user=user, organization=self.org)
        client = APIClient(); client.force_authenticate(user)
        preview = client.post("/api/v1/restore/preview/", {"backup": self.rows, "decisions": {"acme-202403": "add"}}, format="json")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data["periods"][0]["decision"], "add")
        self.assertEqual(preview.data["diff"]["account_item"]["create"], [900])
        applied = client.post("/api/v1/restore/apply/", {"backup": self.rows, "confirm": True, "decisions": {"acme-202403": "add"}}, format="json")
        self.assertEqual(applied.status_code, 200)
        self.assertEqual(AccountItem.objects.count(), 2)

    def test_repeated_missing_line_is_listed_once_and_matches_what_is_added(self):
        self.rows.insert(5, {**self.rows[4], "pk": 902})            # the same missing 5,000 line, twice in the backup
        (period,) = self.plan().periods()
        self.assertEqual(len(period["lines"]), 1)
        result = self.plan().apply({"acme-202403": "add"})
        self.assertEqual(result["added"]["account_item"], 1)


class LegacyRestoreEndpointTests(TestCase):
    """The old /restore/ flushed the whole database, unauthenticated."""

    def test_anonymous_users_cannot_reach_it(self):
        self.assertEqual(self.client.get("/restore/").status_code, 302)
        self.assertEqual(self.client.post("/restore/", {}).status_code, 302)

    def test_post_never_wipes_data_even_when_logged_in(self):
        from django.contrib.auth import get_user_model
        from django.core.files.uploadedfile import SimpleUploadedFile

        org = Organization.objects.create(name="Keep", slug="keep")
        user = get_user_model().objects.create_user("u", password="x")
        self.client.force_login(user)
        response = self.client.post("/restore/", {"json_file": SimpleUploadedFile("b.json", b"[]")})
        self.assertEqual(response.status_code, 410)
        self.assertTrue(Organization.objects.filter(pk=org.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())

    def test_backup_pages_need_a_login(self):
        for url in ("/backup/", "/backup/local/", "/backup/nas/", "/postgres_backup/"):
            self.assertEqual(self.client.get(url).status_code, 302, url)


class SentInvoiceIsFrozenEverywhereTests(TaxCalcTestBase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from .models import OrganizationMembership

        self.kept = self.item(bt=1000, date="2024-03-01", action_name="kept")
        calc.set_invoice_code(self.org)
        calc.total_amount_calc(self.org)
        InvoiceCode.objects.update(sent_at=timezone.now(), tax_rounding="floor")
        user = get_user_model().objects.create_user("u", password="x")
        OrganizationMembership.objects.create(user=user, organization=self.org)
        self.api = APIClient(); self.api.force_authenticate(user)

    def import_rows(self, mode):
        row = {"company": self.client_a.pk, "item_code": self.item_code.pk, "invoice_date": "2024-03-01",
               "action_date": "2024-03-01", "action_name": "new", "invoice_bt": 777}
        return self.api.post("/api/v1/import/", {"account_items": [row], "mode": mode}, format="json")

    def test_import_cannot_add_to_a_sent_period(self):
        response = self.import_rows("create")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created"], 0)
        self.assertIn("already been sent", response.data["errors"][0]["detail"])
        self.assertFalse(AccountItem.objects.filter(action_name="new").exists())

    def test_import_cannot_replace_a_sent_period(self):
        response = self.import_rows("replace")
        self.assertEqual(response.data["created"], 0)
        self.assertTrue(response.data["errors"])
        self.kept.refresh_from_db()                                    # the original line is still there, untouched
        self.assertEqual(AccountItem.objects.filter(action_date=datetime.date(2024, 3, 1)).count(), 1)

    def test_import_into_an_unsent_period_still_works(self):
        InvoiceCode.objects.update(sent_at=None)
        self.assertEqual(self.import_rows("create").data["created"], 1)

    def test_restore_still_protects_a_sent_invoice_after_the_client_slug_changed(self):
        Client.objects.filter(pk=self.client_a.pk).update(slug="renamed")     # invoice key is still "acme-202403"
        rows = RestoreIdCollisionTests.backup_rows(self, item_pk=900, bt=5000)
        rows = [r for r in rows if r["model"] != "invoice.invoicecode"]
        rows[2]["fields"]["slug"] = "renamed"                                  # the backup's client, matched by slug
        result = restore_logic.build_restore_plan(self.org, rows).apply()
        self.assertEqual(result["skipped_sent"]["account_item"], 1)
        self.assertEqual(AccountItem.objects.count(), 1)


class ChangeLogTests(SentInvoiceIsFrozenEverywhereTests):
    # Inherits only the fixture; its inherited tests re-run here, which is harmless.
    """Edits overwrite a line in place; the change log is the only record of what it said before."""

    def logs(self, **filters):
        from .models import ChangeLog
        return ChangeLog.objects.filter(**filters)

    def test_editing_a_line_records_old_and_new_and_who(self):
        response = self.api.patch(f"/api/v1/account-items/{self.kept.pk}/", {"invoice_bt": 2000}, format="json")
        self.assertEqual(response.status_code, 200)
        log = self.logs(object_id=self.kept.pk, action="update").get()
        self.assertEqual(log.changes["invoice_bt"], [1000, 2000])
        self.assertNotIn("action_name", log.changes)          # unchanged fields are not logged
        self.assertEqual(log.username, "u")
        self.assertTrue(log.after_sent)
        self.assertEqual(log.client_name, self.client_a.name)

    def test_a_save_that_changes_nothing_logs_nothing(self):
        self.api.patch(f"/api/v1/account-items/{self.kept.pk}/", {"invoice_bt": 1000}, format="json")
        self.assertFalse(self.logs().exists())

    def test_bulk_update_logs_each_changed_row(self):
        response = self.api.post("/api/v1/account-items/bulk-update/", {"items": [{"id": self.kept.pk, "action_name": "renamed"}]}, format="json")
        self.assertEqual(response.status_code, 200)
        log = self.logs(source="bulk").get()
        self.assertEqual(log.changes["action_name"], ["kept", "renamed"])

    def test_voiding_a_line_on_a_sent_invoice_is_logged_and_keeps_its_values(self):
        self.api.delete(f"/api/v1/account-items/{self.kept.pk}/")
        log = self.logs(action="void").get()
        self.assertEqual(log.changes["invoice_bt"], [1000, None])

    def test_a_physically_deleted_line_still_has_its_history(self):
        InvoiceCode.objects.update(sent_at=None)
        extra = self.item(bt=10, date="2024-03-01", action_name="extra")   # not the invoice's anchor line
        pk = extra.pk
        self.api.delete(f"/api/v1/account-items/{pk}/")
        self.assertFalse(AccountItem.objects.filter(pk=pk).exists())
        log = self.logs(object_id=pk, action="delete").get()
        self.assertEqual(log.changes["action_name"], ["extra", None])
        self.assertIsNone(log.account_item)

    def test_creating_a_line_is_logged(self):
        row = {"company": self.client_a.pk, "item_code": self.item_code.pk, "invoice_date": "2024-03-01",
               "action_date": "2024-03-01", "action_name": "added", "invoice_bt": 50}
        created = self.api.post("/api/v1/account-items/", row, format="json")
        self.assertEqual(created.status_code, 201)
        log = self.logs(action="create").get()
        self.assertEqual(log.changes["invoice_bt"], [None, 50])

    def test_tax_calc_changes_are_logged(self):
        AccountItem.objects.filter(pk=self.kept.pk).update(invoice_at=0, invoice_tax=0)
        calc.apply_tax_calc(self.org, "", "2024-03-01", user=None)
        log = self.logs(source="tax-calc").get()
        self.assertEqual(log.changes["invoice_at"], [0, 1100])

    def test_history_endpoint_is_scoped_and_filterable(self):
        self.api.patch(f"/api/v1/account-items/{self.kept.pk}/", {"invoice_bt": 2000}, format="json")
        data = self.api.get(f"/api/v1/change-log/?item={self.kept.pk}").data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["changes"]["invoice_bt"], [1000, 2000])
        other = Organization.objects.create(name="Other", slug="other")
        from .models import ChangeLog
        ChangeLog.objects.create(organization=other, object_id=1, action="update", changes={"x": [1, 2]})
        self.assertEqual(len(self.api.get("/api/v1/change-log/").data), 1)

    def test_restoring_an_old_dump_writes_no_change_log(self):
        rows = RestoreIdCollisionTests.backup_rows(self, item_pk=900)
        restore_logic.build_restore_plan(self.org, rows).apply()
        self.assertFalse(self.logs().exists())


class TaxCalcDateFieldTests(TaxCalcTestBase):
    def test_line_items_page_matches_on_action_date_not_invoice_date(self):
        line = self.item(bt=1000, date="2024-03-01", action_name="x")
        AccountItem.objects.filter(pk=line.pk).update(action_date=datetime.date(2024, 2, 1), invoice_at=0)
        by_invoice, _ = calc.plan_tax_calc(self.org, "", "2024-02-01")
        by_action, _ = calc.plan_tax_calc(self.org, "", "2024-02-01", "action_date")
        self.assertEqual(len(by_invoice), 0)
        self.assertEqual([r["id"] for r in by_action], [line.pk])

    def test_unknown_date_field_falls_back_to_invoice_date(self):
        line = self.item(bt=1000, date="2024-03-01", action_name="x")
        AccountItem.objects.filter(pk=line.pk).update(invoice_at=0)
        fills, _ = calc.plan_tax_calc(self.org, "", "2024-03-01", "id; drop")
        self.assertEqual(len(fills), 1)


class RestoreToleratesOldDumpsTests(TaxCalcTestBase):
    def test_fields_that_no_longer_exist_in_the_model_are_ignored(self):
        rows = RestoreIdCollisionTests.backup_rows(self, item_pk=900)
        for r in rows:
            if r["model"] in ("invoice.accountitem", "invoice.invoicecode"):
                r["fields"]["field_removed_in_a_later_migration"] = "x"
        result = restore_logic.build_restore_plan(self.org, rows).apply()
        self.assertEqual(result["added"]["account_item"], 1)
        self.assertEqual(result["added"]["invoice_code"], 1)


class AlignmentIgnoresVoidedLinesTests(TaxCalcTestBase):
    def test_a_voided_line_does_not_vote_or_get_rewritten(self):
        keep_a = self.item(bt=1, date="2025-09-01")
        keep_b = self.item(bt=2, date="2025-09-01")
        voided = self.item(bt=3, date="2025-09-15", deleted_at=timezone.now())
        stray = self.item(bt=4, date="2025-09-20")
        changes, ties = calc.plan_invoice_date_alignment(self.org, "", "2025-09-01")
        self.assertEqual([c["id"] for c in changes], [stray.id])          # not the voided one
        self.assertEqual(ties, [])
        calc.apply_invoice_date_alignment(self.org, "", "2025-09-01")
        voided.refresh_from_db()
        self.assertEqual(voided.invoice_date, datetime.date(2025, 9, 15))

    def test_sent_period_is_never_realigned_even_if_the_client_slug_changed(self):
        self.item(bt=1, date="2025-09-01"); self.item(bt=2, date="2025-09-01"); stray = self.item(bt=3, date="2025-09-20")
        calc.set_invoice_code(self.org)
        InvoiceCode.objects.update(sent_at=timezone.now(), tax_rounding="floor")
        Client.objects.filter(pk=self.client_a.pk).update(slug="renamed")
        self.assertEqual(calc.plan_invoice_date_alignment(self.org, "", "2025-09-01"), ([], []))
        stray.refresh_from_db()
        self.assertEqual(stray.invoice_date, datetime.date(2025, 9, 20))


class TotalsAndPdfAlwaysAgreeTests(TaxCalcTestBase):
    def test_random_invoices_totals_equal_pdf_breakdown_for_both_methods(self):
        import random

        rng = random.Random(20260918)
        for round_no in range(60):
            InvoiceCode.objects.all().delete(); AccountItem.objects.all().delete()
            for _ in range(rng.randint(1, 9)):
                self.item(bt=rng.randint(-50000, 200000), rate=rng.choice([0, 8, 10]))
            calc.set_invoice_code(self.org); calc.invoice_code_slug_save(self.org)
            invoice = InvoiceCode.objects.get()
            for method in ("floor", "round"):
                InvoiceCode.objects.filter(pk=invoice.pk).update(tax_rounding=method)
                calc.total_amount_calc(self.org)
                invoice.refresh_from_db()
                rows = calc.prepare_invoice_items(self.org, {"slug": invoice.account_item_slug})["tax_breakdown_rows"]
                taxed = [r for r in rows if r["rate"] != 0]
                ctx = f"round {round_no} {method}"
                self.assertEqual(sum(r["tax"] for r in rows), invoice.invoice_tax_ttl, ctx)
                self.assertEqual(sum(r["base"] for r in taxed), invoice.invoice_bt_ttl, ctx)
                self.assertEqual(sum(r["base"] for r in rows), invoice.invoice_bt_gttl, ctx)
                self.assertEqual(sum(r["total"] for r in rows), invoice.invoice_at_gttl, ctx)
                self.assertEqual(invoice.invoice_at_gttl, invoice.invoice_bt_gttl + invoice.invoice_tax_ttl, ctx)


class MovingLinesBetweenInvoicesTests(TaxCalcTestBase):
    """An invoice is one client + one month; editing a line's client or date can move it."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from .models import OrganizationMembership

        self.beta = Client.objects.create(organization=self.org, name="Beta", short_name="beta", slug="beta", bank_account=self.client_a.bank_account)
        self.l1 = self.item(bt=1000, date="2025-09-01", action_name="l1")   # becomes the invoice's anchor
        self.l2 = self.item(bt=2000, date="2025-09-01", action_name="l2")
        self.l3 = self.item(bt=4000, date="2025-09-01", action_name="l3")
        self.refresh_pipeline()
        user = get_user_model().objects.create_user("u", password="x")
        OrganizationMembership.objects.create(user=user, organization=self.org)
        self.api = APIClient(); self.api.force_authenticate(user)

    def refresh_pipeline(self):
        calc.set_invoice_code(self.org); calc.invoice_code_slug_save(self.org); calc.total_amount_calc(self.org)

    def invoice(self, slug):
        return InvoiceCode.objects.get(account_item_slug=slug)

    def patch(self, item, **data):
        return self.api.patch(f"/api/v1/account-items/{item.pk}/", data, format="json")

    def test_setup_anchor_is_first_line(self):
        self.assertEqual(self.invoice("acme-202509").account_item_id, self.l1.pk)

    def test_moving_a_line_to_another_month_leaves_the_old_total_and_joins_the_new_invoice(self):
        self.assertEqual(self.patch(self.l2, invoice_date="2025-10-01").status_code, 200)
        self.refresh_pipeline()
        self.assertEqual(self.invoice("acme-202509").invoice_bt_ttl, 5000)      # l2's 2000 is gone from September
        self.assertEqual(self.invoice("acme-202510").invoice_bt_ttl, 2000)      # and counted in October
        self.assertEqual(self.reload(self.l2).slug, "acme-202510")

    def test_moving_a_line_to_another_client_follows_it(self):
        self.assertEqual(self.patch(self.l3, company=self.beta.pk).status_code, 200)
        self.refresh_pipeline()
        self.assertEqual(self.invoice("acme-202509").invoice_bt_ttl, 3000)
        self.assertEqual(self.invoice("beta-202509").invoice_bt_ttl, 4000)

    def test_moving_the_anchor_line_repoints_the_old_invoice(self):
        self.assertEqual(self.patch(self.l1, invoice_date="2025-10-01").status_code, 200)
        old = self.invoice("acme-202509")
        self.assertNotEqual(old.account_item_id, self.l1.pk)
        self.assertEqual(old.account_item.invoice_date, datetime.date(2025, 9, 1))     # still anchored inside September
        self.refresh_pipeline()
        self.assertEqual(self.invoice("acme-202509").invoice_bt_ttl, 6000)
        self.assertEqual(self.invoice("acme-202510").invoice_bt_ttl, 1000)

    def test_a_date_change_inside_the_same_month_stays_on_the_same_invoice(self):
        self.assertEqual(self.patch(self.l2, invoice_date="2025-09-15").status_code, 200)
        self.assertEqual(self.reload(self.l2).slug, "acme-202509")

    def test_the_only_line_of_an_invoice_cannot_be_moved_away(self):
        lone = self.item(bt=500, date="2025-11-01")
        self.refresh_pipeline()
        response = self.patch(lone, invoice_date="2025-12-01")
        self.assertEqual(response.status_code, 400)
        self.assertIn("only line", str(response.data))
        self.assertEqual(self.reload(lone).invoice_date, datetime.date(2025, 11, 1))

    def test_a_sent_invoices_lines_cannot_change_client_or_date(self):
        InvoiceCode.objects.filter(account_item_slug="acme-202509").update(sent_at=timezone.now(), tax_rounding="floor")
        self.assertIn("company", self.patch(self.l2, company=self.beta.pk).data)
        self.assertIn("invoice_date", self.patch(self.l2, invoice_date="2025-10-01").data)
        self.assertIn("invoice_date", self.patch(self.l2, invoice_date="2025-09-15").data)
        l2 = self.reload(self.l2)
        self.assertEqual((l2.company_id, l2.invoice_date), (self.client_a.pk, datetime.date(2025, 9, 1)))

    def test_editing_an_amount_on_a_sent_invoice_is_still_allowed_and_marks_it_amended(self):
        InvoiceCode.objects.filter(account_item_slug="acme-202509").update(sent_at=timezone.now(), tax_rounding="floor")
        self.assertEqual(self.patch(self.l2, invoice_bt=2500).status_code, 200)
        self.assertTrue(self.invoice("acme-202509").amended)

    def test_nothing_can_be_moved_into_a_sent_invoice(self):
        oct_line = self.item(bt=100, date="2025-10-01"); self.refresh_pipeline()
        InvoiceCode.objects.filter(account_item_slug="acme-202510").update(sent_at=timezone.now(), tax_rounding="floor")
        response = self.patch(self.l2, invoice_date="2025-10-01")
        self.assertEqual(response.status_code, 400)
        self.assertIn("already been sent", str(response.data))
        self.assertEqual(self.reload(self.l2).invoice_date, datetime.date(2025, 9, 1))

    def test_bulk_update_moves_several_lines_at_once(self):
        response = self.api.post("/api/v1/account-items/bulk-update/", {"items": [
            {"id": self.l2.pk, "invoice_date": "2025-10-01"}, {"id": self.l3.pk, "invoice_date": "2025-10-01"}]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.refresh_pipeline()
        self.assertEqual(self.invoice("acme-202509").invoice_bt_ttl, 1000)
        self.assertEqual(self.invoice("acme-202510").invoice_bt_ttl, 6000)

    def test_bulk_update_that_would_empty_an_invoice_is_refused_and_changes_nothing(self):
        response = self.api.post("/api/v1/account-items/bulk-update/", {"items": [
            {"id": self.l1.pk, "invoice_date": "2025-10-01"}, {"id": self.l2.pk, "invoice_date": "2025-10-01"},
            {"id": self.l3.pk, "invoice_date": "2025-10-01"}]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("only line", str(response.data))
        for line in (self.l1, self.l2, self.l3):
            self.assertEqual(self.reload(line).invoice_date, datetime.date(2025, 9, 1))
        self.assertEqual(self.invoice("acme-202509").account_item_id, self.l1.pk)          # anchor untouched


class InvoicePdfShowsEachLinesTargetMonthTests(TaxCalcTestBase):
    def html_for(self, *lines):
        for bt, action_date, name, note in lines:
            line = self.item(bt=bt, date="2026-08-01", action_name=name, action_note=note)
            AccountItem.objects.filter(pk=line.pk).update(action_date=datetime.date.fromisoformat(action_date))
        calc.set_invoice_code(self.org); calc.invoice_code_slug_save(self.org); calc.total_amount_calc(self.org)
        return calc.prepare_invoice_items(self.org, {"slug": "acme-202608"})["html_content"]

    def test_every_line_shows_its_own_action_month_between_item_name_and_description(self):
        html = self.html_for((504320, "2026-07-01", "立替：電力", "東京電力"), (1800, "2026-06-01", "業務委託費", "追加分"))
        rows = [r for r in html.split("<tr>") if "立替：電力" in r or "業務委託費" in r]
        self.assertEqual(len(rows), 2)
        power = next(r for r in rows if "立替：電力" in r)
        fee = next(r for r in rows if "業務委託費" in r)
        self.assertIn("2026年7月分", power)
        self.assertIn("2026年6月分", fee)
        self.assertLess(power.index("立替：電力"), power.index("2026年7月分"))     # 品目 -> 対象月
        self.assertLess(power.index("2026年7月分"), power.index("東京電力"))       # 対象月 -> 内容・摘要
        self.assertLess(html.index("<th>品目</th>"), html.index("<th>対象月</th>"))
        self.assertLess(html.index("<th>対象月</th>"), html.index("<th>内容・摘要</th>"))

    def test_header_no_longer_repeats_the_target_month(self):
        # 対象月 is shown once per line in the table; the header only has number + issue date.
        html = self.html_for((100, "2026-07-01", "a", ""), (200, "2026-06-01", "b", ""))
        self.assertNotIn("対象月　", html)
        self.assertIn("2026年6月分", html)
        self.assertIn("2026年7月分", html)
