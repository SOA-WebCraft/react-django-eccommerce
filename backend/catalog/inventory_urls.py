from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .inventory_views import (
    InventoryStockListView,
    PurchaseOrderCancelView,
    PurchaseOrderDetailView,
    PurchaseOrderListCreateView,
    PurchaseOrderReceiveView,
    StockAdjustmentView,
    StockMovementListView,
    SupplierViewSet,
)


router = DefaultRouter()
router.register('suppliers', SupplierViewSet, basename='inventory-supplier')

urlpatterns = [
    path('stock/', InventoryStockListView.as_view(), name='inventory-stock'),
    path('adjustments/', StockAdjustmentView.as_view(), name='stock-adjustment'),
    path('movements/', StockMovementListView.as_view(), name='stock-movement-list'),
    path(
        'purchase-orders/',
        PurchaseOrderListCreateView.as_view(),
        name='purchase-order-list',
    ),
    path(
        'purchase-orders/<int:pk>/',
        PurchaseOrderDetailView.as_view(),
        name='purchase-order-detail',
    ),
    path(
        'purchase-orders/<int:pk>/receive/',
        PurchaseOrderReceiveView.as_view(),
        name='purchase-order-receive',
    ),
    path(
        'purchase-orders/<int:pk>/cancel/',
        PurchaseOrderCancelView.as_view(),
        name='purchase-order-cancel',
    ),
    path('', include(router.urls)),
]
