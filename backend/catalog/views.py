from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models.deletion import ProtectedError
from rest_framework import filters, generics, mixins, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from .models import Category, Product, ProductImage
from .permissions import (
    HasCatalogModelPermissionsOrReadOnly,
    can_manage_catalog,
)
from .serializers import (
    CategorySerializer,
    ProductGalleryUploadSerializer,
    ProductImageSerializer,
    ProductSerializer,
)


class PatchOnlyModelViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def perform_update(self, serializer):
        serializer.save()


class CategoryViewSet(PatchOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (HasCatalogModelPermissionsOrReadOnly,)
    permission_model = Category
    http_method_names = (
        'get',
        'post',
        'put',
        'patch',
        'delete',
        'head',
        'options',
    )

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError(
                {'detail': 'Categories with products cannot be deleted.'}
            ) from exc


class ProductViewSet(PatchOnlyModelViewSet):
    serializer_class = ProductSerializer
    lookup_field = 'slug'
    permission_classes = (HasCatalogModelPermissionsOrReadOnly,)
    permission_model = Product
    http_method_names = (
        'get',
        'post',
        'put',
        'patch',
        'delete',
        'head',
        'options',
    )
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('name',)
    ordering_fields = ('name', 'price', 'created_at')
    ordering = ('name',)

    def get_queryset(self):
        queryset = Product.objects.select_related(
            'category'
        ).prefetch_related('gallery_images')
        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(is_active=True)

        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)

        active = self.request.query_params.get('is_active')
        if active is not None and can_manage_catalog(self.request.user):
            normalized = active.lower()
            if normalized not in ('true', 'false'):
                raise ValidationError(
                    {'is_active': 'Must be either true or false.'}
                )
            queryset = queryset.filter(is_active=normalized == 'true')

        for parameter, lookup in (
            ('min_price', 'price__gte'),
            ('max_price', 'price__lte'),
        ):
            value = self.request.query_params.get(parameter)
            if value is not None:
                try:
                    value = Decimal(value)
                except InvalidOperation as exc:
                    raise ValidationError(
                        {parameter: 'Must be a valid decimal number.'}
                    ) from exc
                if value < 0:
                    raise ValidationError(
                        {parameter: 'Must be zero or greater.'}
                    )
                queryset = queryset.filter(**{lookup: value})
        return queryset


class ProductImageListCreateView(generics.GenericAPIView):
    permission_classes = (HasCatalogModelPermissionsOrReadOnly,)
    permission_model = ProductImage
    serializer_class = ProductGalleryUploadSerializer

    def get_product_queryset(self):
        queryset = Product.objects.all()
        if not can_manage_catalog(self.request.user):
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_product(self):
        try:
            return self.get_product_queryset().get(
                pk=self.kwargs['product_pk']
            )
        except Product.DoesNotExist as exc:
            raise NotFound('Product not found.') from exc

    def get(self, request, *args, **kwargs):
        product = self.get_product()
        images = product.gallery_images.all()
        serializer = ProductImageSerializer(
            images,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            product = Product.objects.select_for_update().get(
                pk=self.get_product().pk
            )
            existing_count = product.gallery_images.count()
            upload_count = len(serializer.validated_data['images'])
            if existing_count + upload_count > 10:
                raise ValidationError(
                    {'images': 'A product may have at most 10 gallery images.'}
                )
            images = serializer.save(product=product)
        output = ProductImageSerializer(
            images,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(output.data, status=status.HTTP_201_CREATED)


class ProductImageDeleteView(generics.DestroyAPIView):
    permission_classes = (HasCatalogModelPermissionsOrReadOnly,)
    permission_model = ProductImage
    serializer_class = ProductImageSerializer
    lookup_url_kwarg = 'image_pk'

    def get_queryset(self):
        return ProductImage.objects.filter(
            product_id=self.kwargs['product_pk']
        )
