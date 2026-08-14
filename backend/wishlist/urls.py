from django.urls import path

from .views import WishlistItemDeleteView, WishlistListCreateView


urlpatterns = [
    path('wishlist/', WishlistListCreateView.as_view(), name='wishlist-list'),
    path(
        'wishlist/items/<int:pk>/',
        WishlistItemDeleteView.as_view(),
        name='wishlist-item-delete',
    ),
]
