from django.db import transaction
from django.db.models import F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce, Greatest
from django.db.models.deletion import ProtectedError
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import CheckoutAttempt

from .inventory_serializers import (
    InventoryProductSerializer,
    PurchaseOrderSerializer,
    StockAdjustmentSerializer,
    StockMovementSerializer,
    SupplierSerializer,
)
from .inventory_services import adjust_stock, receive_purchase_order
from .models import Product, PurchaseOrder, StockMovement, Supplier


class InventoryStockListView(generics.ListAPIView):
    serializer_class = InventoryProductSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        queryset = (
            Product.objects.select_related('category')
            .annotate(
                reserved_stock=Coalesce(
                    Sum(
                        'checkoutitem__quantity',
                        filter=Q(checkoutitem__checkout__status__in=(
                            CheckoutAttempt.Status.CREATED,
                            CheckoutAttempt.Status.PAID,
                        )),
                    ),
                    Value(0),
                    output_field=IntegerField(),
                )
            )
            .annotate(
                available_stock_db=Greatest(
                    F('stock_quantity') - F('reserved_stock'),
                    Value(0),
                )
            )
            .order_by('name')
        )
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(name__icontains=search)
        state = self.request.query_params.get('state')
        if state == 'out_of_stock':
            queryset = queryset.filter(available_stock_db=0)
        elif state == 'low_stock':
            queryset = queryset.filter(
                available_stock_db__gt=0,
                available_stock_db__lte=F('minimum_stock_quantity'),
            )
        elif state == 'in_stock':
            queryset = queryset.filter(
                available_stock_db__gt=F('minimum_stock_quantity')
            )
        elif state:
            raise ValidationError({
                'state': 'Must be in_stock, low_stock, or out_of_stock.'
            })
        return queryset


class StockAdjustmentView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request):
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movement = adjust_stock(request.user, serializer.validated_data)
        return Response(
            StockMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )


class StockMovementListView(generics.ListAPIView):
    serializer_class = StockMovementSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        queryset = StockMovement.objects.select_related('product', 'created_by')
        product = self.request.query_params.get('product')
        if product:
            queryset = queryset.filter(product_id=product)
        return queryset


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = Supplier.objects.prefetch_related('products')
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError({
                'detail': 'Suppliers with purchase orders cannot be deleted.'
            }) from exc


class PurchaseOrderListCreateView(generics.ListCreateAPIView):
    serializer_class = PurchaseOrderSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related(
            'supplier', 'created_by'
        ).prefetch_related('items__product')
        order_status = self.request.query_params.get('status')
        if order_status:
            if order_status not in PurchaseOrder.Status.values:
                raise ValidationError({'status': 'Invalid purchase order status.'})
            queryset = queryset.filter(status=order_status)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save()


class PurchaseOrderDetailView(generics.RetrieveAPIView):
    serializer_class = PurchaseOrderSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = PurchaseOrder.objects.select_related(
        'supplier', 'created_by'
    ).prefetch_related('items__product')


class PurchaseOrderReceiveView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, pk):
        try:
            order = receive_purchase_order(request.user, pk)
        except PurchaseOrder.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Purchase order not found.')
        order = PurchaseOrderDetailView.queryset.get(pk=order.pk)
        return Response(PurchaseOrderSerializer(order).data)


class PurchaseOrderCancelView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = PurchaseOrder.objects.select_for_update().get(pk=pk)
        except PurchaseOrder.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Purchase order not found.')
        if order.status != PurchaseOrder.Status.ORDERED:
            raise ValidationError({
                'status': 'Only an ordered purchase order can be cancelled.'
            })
        order.status = PurchaseOrder.Status.CANCELLED
        order.save(update_fields=('status',))
        order = PurchaseOrderDetailView.queryset.get(pk=order.pk)
        return Response(PurchaseOrderSerializer(order).data)
