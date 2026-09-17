"""
Full, per-organization restore from a Django `dumpdata` JSON backup (the
same format already produced by backup_logic.dump_postgres_to_json_to_nas
and by `python manage.py dumpdata`).

Unlike the old `restore_view` (which did a global `flush` + `loaddata` and
therefore wiped every organization and every user), this only ever reads or
writes the rows that belong to ONE organization, matched by `slug` rather
than by raw id (backup and live ids only line up if it's the same install
lineage, and matching by slug catches it if they ever don't). Auth/
membership rows (User, OrganizationMembership) are never part of the
restorable set - who has access to an organization is never something a
data restore should be able to change.

Two-step by design: `build_restore_plan` + `RestorePlan.diff()` is entirely
read-only and safe to call as often as you like; `RestorePlan.apply()` is
the only thing that writes, and refuses to write anything at all if it
finds a single pk conflicting with another organization's data.
"""
import json
from dataclasses import dataclass, field

from django.core.management.color import no_style
from django.core.serializers import deserialize
from django.db import connections, transaction

from .models import AccountItem, BankAccount, Client, InvoiceCode, ItemCode, Organization


class RestoreError(Exception):
    pass


def _fields_for(row):
    return row["fields"]


def _index_by_model(fixture_rows):
    by_model = {}
    for row in fixture_rows:
        by_model.setdefault(row.get("model"), []).append(row)
    return by_model


def _model_conflicts(Model, rows, organization, org_field="organization"):
    """pks in `rows` that already exist live under a DIFFERENT organization."""
    conflicts = []
    for row in rows:
        obj = Model.objects.filter(pk=row["pk"]).exclude(**{org_field: organization}).first()
        if obj is not None:
            conflicts.append({"model": Model._meta.label_lower, "pk": row["pk"]})
    return conflicts


def _bank_account_conflicts(rows, organization):
    conflicts = []
    for row in rows:
        pk = row["pk"]
        if not BankAccount.objects.filter(pk=pk).exists():
            continue
        used_elsewhere = (
            Client.objects.filter(bank_account_id=pk).exclude(organization=organization).exists()
            or Organization.objects.exclude(pk=organization.pk).filter(bank_account_id=pk).exists()
        )
        if used_elsewhere:
            conflicts.append({"model": "invoice.bankaccount", "pk": pk})
    return conflicts


@dataclass
class ModelChange:
    label: str
    create: list = field(default_factory=list)   # pks
    update: list = field(default_factory=list)   # pks (already exist for this org)
    delete: list = field(default_factory=list)   # pks (live for this org, absent from backup)


@dataclass
class RestorePlan:
    organization: Organization
    backup_org_pk: int
    organization_row: dict
    bank_account_rows: list
    item_code_rows: list
    client_rows: list
    account_item_rows: list
    invoice_code_rows: list

    def conflicts(self):
        return (
            _bank_account_conflicts(self.bank_account_rows, self.organization)
            + _model_conflicts(ItemCode, self.item_code_rows, self.organization)
            + _model_conflicts(Client, self.client_rows, self.organization)
            + _model_conflicts(AccountItem, self.account_item_rows, self.organization)
            + _model_conflicts(InvoiceCode, self.invoice_code_rows, self.organization, org_field="account_item__organization")
        )

    def _change_for(self, Model, rows, org_filter_kwargs, label):
        backup_pks = {row["pk"] for row in rows}
        live_pks = set(Model.objects.filter(**org_filter_kwargs).values_list("pk", flat=True))
        return ModelChange(
            label=label,
            create=sorted(backup_pks - live_pks),
            update=sorted(backup_pks & live_pks),
            delete=sorted(live_pks - backup_pks),
        )

    def diff(self):
        """Read-only summary of what apply() would do. Never writes."""
        return {
            # The live Organization row is always updated in place (matched
            # by slug already), never created or deleted by a restore.
            "organization": {"label": "invoice.organization", "create": [], "update": [self.organization.pk], "delete": []},
            "bank_account": [row["pk"] for row in self.bank_account_rows],
            "item_code": self._change_for(ItemCode, self.item_code_rows, {"organization": self.organization}, "invoice.itemcode").__dict__,
            "client": self._change_for(Client, self.client_rows, {"organization": self.organization}, "invoice.client").__dict__,
            "account_item": self._change_for(AccountItem, self.account_item_rows, {"organization": self.organization}, "invoice.accountitem").__dict__,
            "invoice_code": self._change_for(
                InvoiceCode, self.invoice_code_rows, {"account_item__organization": self.organization}, "invoice.invoicecode"
            ).__dict__,
        }

    def apply(self):
        conflicts = self.conflicts()
        if conflicts:
            raise RestoreError(
                "Refusing to restore: some rows in this backup share an id with another "
                "organization's data. Nothing was changed. Conflicts: " + json.dumps(conflicts)
            )

        with transaction.atomic():
            # 1) Upsert everything the backup says should exist, in FK order,
            #    using the backup's own pks (so invoice numbers, which are
            #    derived from InvoiceCode's own id, come back unchanged).
            _upsert_rows(self.bank_account_rows)
            _apply_organization_fields(self.organization, _fields_for(self.organization_row))
            _upsert_rows(self.item_code_rows)
            _upsert_rows(self.client_rows)
            _upsert_rows(self.account_item_rows)
            # Repoints InvoiceCode.account_item back to the backup's original
            # target *before* anything not in the backup gets deleted below,
            # which is what keeps the PROTECT constraint from ever firing.
            _upsert_rows(self.invoice_code_rows)

            # 2) Now remove anything that exists live for this org but isn't
            #    in the backup, in reverse FK order.
            invoice_code_delete = InvoiceCode.objects.filter(
                account_item__organization=self.organization
            ).exclude(pk__in=[r["pk"] for r in self.invoice_code_rows])
            invoice_code_deleted = invoice_code_delete.count()
            invoice_code_delete.delete()

            account_item_delete = AccountItem.objects.filter(organization=self.organization).exclude(
                pk__in=[r["pk"] for r in self.account_item_rows]
            )
            account_item_deleted = account_item_delete.count()
            account_item_delete.delete()

            client_delete = Client.objects.filter(organization=self.organization).exclude(
                pk__in=[r["pk"] for r in self.client_rows]
            )
            client_deleted = client_delete.count()
            client_delete.delete()

            item_code_delete = ItemCode.objects.filter(organization=self.organization).exclude(
                pk__in=[r["pk"] for r in self.item_code_rows]
            )
            item_code_deleted = item_code_delete.count()
            item_code_delete.delete()

            # 3) Explicit pks were just inserted directly - on backends with
            #    a real sequence (Postgres) that sequence hasn't advanced,
            #    so the next auto-assigned id could collide with one we just
            #    restored. No-op on SQLite (nextval tracks max(rowid) already).
            _reset_sequences([BankAccount, ItemCode, Client, AccountItem, InvoiceCode])

        return {
            "bank_account": len(self.bank_account_rows),
            "item_code": len(self.item_code_rows),
            "client": len(self.client_rows),
            "account_item": len(self.account_item_rows),
            "invoice_code": len(self.invoice_code_rows),
            "deleted": {
                "invoice_code": invoice_code_deleted,
                "account_item": account_item_deleted,
                "client": client_deleted,
                "item_code": item_code_deleted,
            },
        }


def build_restore_plan(organization, fixture_rows):
    by_model = _index_by_model(fixture_rows)

    org_rows = [r for r in by_model.get("invoice.organization", []) if _fields_for(r).get("slug") == organization.slug]
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

    bank_account_pks = {_fields_for(backup_org_row).get("bank_account")}
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


def _upsert_rows(rows):
    """Create-or-overwrite each row at its own backup pk, via Django's own
    fixture deserializer so field type coercion (dates, FKs, ...) matches
    `loaddata` exactly instead of a hand-rolled setattr loop."""
    if not rows:
        return
    for deserialized in deserialize("json", json.dumps(rows)):
        deserialized.save()


def _apply_organization_fields(organization, backup_fields):
    """The live Organization row is never replaced (its pk is what every
    other table already points to) - just its own fields are overwritten
    from the backup, skipping the id and anything that isn't a plain field
    on this model (e.g. reverse relations don't appear in `fields` anyway)."""
    for name, value in backup_fields.items():
        model_field = Organization._meta.get_field(name)
        if model_field.is_relation:
            setattr(organization, model_field.attname, value)
        else:
            setattr(organization, name, model_field.to_python(value) if value is not None else None)
    organization.save()


def _reset_sequences(models):
    connection = connections["default"]
    with connection.cursor() as cursor:
        for statement in connection.ops.sequence_reset_sql(no_style(), models):
            cursor.execute(statement)
