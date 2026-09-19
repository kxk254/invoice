"""
Change-log helpers. Call snapshot(item) before an edit and record_change()
after it; only fields that actually differ are written, so a save that
changed nothing leaves no entry.
"""
from .models import ChangeLog

TRACKED_FIELDS = [
    "company", "invoice_date", "payment_due", "action_date", "action_name",
    "action_note", "item_code", "tax_rate", "invoice_bt", "invoice_tax", "invoice_at",
]


def snapshot(item):
    """Plain, JSON-safe copy of the audited fields (FKs by readable name)."""
    values = {}
    for name in TRACKED_FIELDS:
        if name == "company":
            value = item.company.name
        elif name == "item_code":
            value = item.item_code.slug
        else:
            value = getattr(item, name)
            value = value.isoformat() if hasattr(value, "isoformat") else value
        values[name] = value
    return values


def record_change(organization, item, action, before=None, after=None, user=None, source="", after_sent=False):
    before, after = before or {}, after or {}
    if action == ChangeLog.Action.UPDATE:
        changes = {k: [before[k], after[k]] for k in after if before.get(k) != after[k]}
        if not changes:
            return None
    elif action == ChangeLog.Action.CREATE:
        changes = {k: [None, v] for k, v in after.items()}
    else:  # void / delete: keep the last known values
        changes = {k: [v, None] for k, v in before.items()}
    return ChangeLog.objects.create(
        organization=organization,
        account_item=item,
        object_id=item.pk,
        action=action,
        source=source,
        changes=changes,
        client_name=item.company.name,
        invoice_slug=item.slug or "",
        after_sent=after_sent,
        user=user if getattr(user, "is_authenticated", False) else None,
        username=getattr(user, "username", "") if getattr(user, "is_authenticated", False) else "",
    )
