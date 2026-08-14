from django.urls import path

from .consumers import StaffAnalyticsConsumer


websocket_urlpatterns = [
    path(
        'ws/staff/analytics/',
        StaffAnalyticsConsumer.as_asgi(),
        name='staff-analytics-websocket',
    ),
]
