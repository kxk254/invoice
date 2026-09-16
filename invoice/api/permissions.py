from rest_framework.exceptions import PermissionDenied


def get_active_organization(user):
    """
    v1 assumption: a user belongs to exactly one Organization. If they ever
    need to belong to more than one (e.g. an accountant serving several SME
    clients), this is the place to add an org-switcher instead of "first".
    """
    membership = user.memberships.select_related("organization").first()
    if membership is None:
        raise PermissionDenied("User is not a member of any organization.")
    return membership.organization


class OrganizationScopedMixin:
    """
    Resolves request.organization and scopes the viewset's queryset/creates
    to it. Must come before authentication succeeds, so it hooks into
    initial() (after DRF's own auth/permission checks have already run).

    `organization_lookup` lets a viewset whose model has no direct
    `organization` FK (e.g. InvoiceCode, reached via account_item__organization)
    scope through a related field instead.
    """

    organization_lookup = "organization"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        request.organization = get_active_organization(request.user)

    def get_queryset(self):
        return self.queryset.filter(**{self.organization_lookup: self.request.organization})

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)
