from rest_framework import permissions


class HasCatalogModelPermissionsOrReadOnly(permissions.BasePermission):
    permission_actions = {
        'POST': 'add',
        'PUT': 'change',
        'PATCH': 'change',
        'DELETE': 'delete',
    }

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        model = view.permission_model
        action = self.permission_actions.get(request.method)
        permission = (
            f'{model._meta.app_label}.'
            f'{action}_{model._meta.model_name}'
        )
        return request.user.has_perm(permission)


class ProductReviewPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, review):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == 'DELETE' and request.user.is_staff:
            return True
        return review.user_id == request.user.id


def can_manage_catalog(user):
    return bool(
        user
        and user.is_authenticated
        and user.has_perm('catalog.change_product')
    )
