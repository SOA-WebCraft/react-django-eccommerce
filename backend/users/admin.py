from django.contrib import admin

from .models import MobileSocialExchange, Profile, SocialIdentity


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'phone', 'updated_at')
    search_fields = ('user__username', 'user__email', 'first_name', 'last_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SocialIdentity)
class SocialIdentityAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'email', 'created_at')
    list_filter = ('provider',)
    search_fields = ('user__username', 'user__email', 'email', 'subject')
    readonly_fields = ('user', 'provider', 'subject', 'email', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MobileSocialExchange)
class MobileSocialExchangeAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'expires_at', 'consumed_at', 'created_at')
    list_filter = ('provider',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = (
        'user', 'provider', 'code_hash', 'redirect_uri', 'expires_at',
        'consumed_at', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
