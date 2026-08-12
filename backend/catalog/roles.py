from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


CATALOG_MANAGERS_GROUP = 'Catalog Managers'
CATALOG_PERMISSION_CODENAMES = (
    'add_category',
    'change_category',
    'delete_category',
    'add_product',
    'change_product',
    'delete_product',
    'add_productimage',
    'change_productimage',
    'delete_productimage',
)


@receiver(post_migrate)
def create_catalog_managers_group(sender, **kwargs):
    if sender.name != 'catalog':
        return
    group, _ = Group.objects.get_or_create(name=CATALOG_MANAGERS_GROUP)
    permissions = Permission.objects.filter(
        content_type__app_label='catalog',
        codename__in=CATALOG_PERMISSION_CODENAMES,
    )
    group.permissions.set(permissions)
