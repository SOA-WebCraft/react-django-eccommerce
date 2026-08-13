from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    first_name = models.CharField(max_length=150, null=True, blank=True)
    last_name = models.CharField(max_length=150, null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=120, null=True, blank=True)
    postal_code = models.CharField(max_length=40, null=True, blank=True)
    country = models.CharField(max_length=120, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Profile for {self.user}'


class SocialIdentity(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = 'google', 'Google'
        APPLE = 'apple', 'Apple'
        FACEBOOK = 'facebook', 'Facebook'
        LINKEDIN = 'linkedin', 'LinkedIn'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='social_identities',
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    subject = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('provider', 'subject'),
                name='unique_social_provider_subject',
            ),
        ]

    def __str__(self):
        return f'{self.get_provider_display()} identity for {self.user}'
