from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    CategoryViewSet,
    ProductImageDeleteView,
    ProductImageListCreateView,
    ProductViewSet,
)


router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('products', ProductViewSet, basename='product')

urlpatterns = [
    path(
        'products/<int:product_pk>/images/',
        ProductImageListCreateView.as_view(),
        name='product-image-list-create',
    ),
    path(
        'products/<int:product_pk>/images/<int:image_pk>/',
        ProductImageDeleteView.as_view(),
        name='product-image-delete',
    ),
    *router.urls,
]
