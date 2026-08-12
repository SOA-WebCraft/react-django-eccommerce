from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Product, ProductImage


def delete_file_if_unreferenced(storage, name):
    referenced = (
        Product.objects.filter(image=name).exists()
        or ProductImage.objects.filter(image=name).exists()
    )
    if name and not referenced:
        storage.delete(name)


def schedule_file_deletion(field_file):
    if not field_file or not field_file.name:
        return
    storage = field_file.storage
    name = field_file.name
    transaction.on_commit(
        lambda: delete_file_if_unreferenced(storage, name)
    )


@receiver(pre_save, sender=Product)
def delete_replaced_product_image(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    previous_name = previous.image.name if previous.image else None
    current_name = instance.image.name if instance.image else None
    if previous_name and previous_name != current_name:
        schedule_file_deletion(previous.image)


@receiver(post_delete, sender=Product)
def delete_removed_product_image(sender, instance, **kwargs):
    schedule_file_deletion(instance.image)


@receiver(pre_save, sender=ProductImage)
def delete_replaced_gallery_image(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    previous_name = previous.image.name if previous.image else None
    current_name = instance.image.name if instance.image else None
    if previous_name and previous_name != current_name:
        schedule_file_deletion(previous.image)


@receiver(post_delete, sender=ProductImage)
def delete_removed_gallery_image(sender, instance, **kwargs):
    schedule_file_deletion(instance.image)
