from django.urls import path

from .views import (
    StaffCustomerDetailView,
    StaffCustomerListView,
    StaffSettingsPermissionListView,
    StaffSettingsRoleDetailView,
    StaffSettingsRoleListView,
    StaffSettingsUserDetailView,
    StaffSettingsUserListView,
)


urlpatterns = [
    path('settings/users/', StaffSettingsUserListView.as_view(), name='staff-settings-user-list'),
    path('settings/users/<int:pk>/', StaffSettingsUserDetailView.as_view(), name='staff-settings-user-detail'),
    path('settings/roles/', StaffSettingsRoleListView.as_view(), name='staff-settings-role-list'),
    path('settings/roles/permissions/', StaffSettingsPermissionListView.as_view(), name='staff-settings-permissions'),
    path('settings/roles/<int:pk>/', StaffSettingsRoleDetailView.as_view(), name='staff-settings-role-detail'),
    path('customers/', StaffCustomerListView.as_view(), name='staff-customer-list'),
    path(
        'customers/<int:pk>/',
        StaffCustomerDetailView.as_view(),
        name='staff-customer-detail',
    ),
]
