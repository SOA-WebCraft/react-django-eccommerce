from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, Prefetch, Value
from django.db.models.functions import Coalesce
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from catalog.models import Product

from .models import WishlistItem
from .serializers import WishlistItemSerializer


def wishlist_product_queryset():
    return Product.objects.select_related('category').prefetch_related(
        'gallery_images',
    ).annotate(
        rating_average=Coalesce(
            Avg('reviews__rating'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=3, decimal_places=2),
        ),
        review_count=Count('reviews', distinct=True),
    )


class WishlistListCreateView(generics.ListCreateAPIView):
    serializer_class = WishlistItemSerializer
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        return WishlistItem.objects.filter(
            user=self.request.user,
        ).prefetch_related(Prefetch(
            'product',
            queryset=wishlist_product_queryset(),
        ))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        response_status = (
            status.HTTP_201_CREATED
            if serializer.was_created
            else status.HTTP_200_OK
        )
        return Response(serializer.data, status=response_status)


class WishlistItemDeleteView(generics.DestroyAPIView):
    serializer_class = WishlistItemSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return WishlistItem.objects.filter(user=self.request.user)
