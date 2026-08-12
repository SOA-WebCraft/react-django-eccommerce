from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Cart, CartItem
from .serializers import (
    CartItemQuantityAdjustmentSerializer,
    CartItemSerializer,
    CartSerializer,
)


class CartView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return Cart.objects.prefetch_related(
            'items__product__category'
        ).get(pk=cart.pk)


class CartItemCreateView(generics.CreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        response_status = (
            status.HTTP_201_CREATED
            if serializer.was_created
            else status.HTTP_200_OK
        )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=response_status, headers=headers)


class CartItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartItemSerializer
    permission_classes = (permissions.IsAuthenticated,)
    http_method_names = ('patch', 'delete', 'options')

    def get_queryset(self):
        return CartItem.objects.filter(
            cart__user=self.request.user
        ).select_related('product__category')

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        queryset = self.filter_queryset(
            self.get_queryset().select_for_update()
        )
        item = get_object_or_404(queryset, pk=kwargs['pk'])
        adjustment = CartItemQuantityAdjustmentSerializer(
            data=request.data,
            context={'item': item},
        )
        adjustment.is_valid(raise_exception=True)
        delta = (
            1
            if adjustment.validated_data['operation'] == 'increment'
            else -1
        )
        item.quantity += delta
        item.save(update_fields=('quantity',))
        return Response(
            CartItemSerializer(item, context={'request': request}).data
        )
