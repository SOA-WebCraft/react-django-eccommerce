from PIL import Image
from rest_framework import serializers

from orders.models import OrderItem

from .models import Category, Product, ProductImage, ProductReview


class ValidatedProductImageField(serializers.ImageField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                'Image size must not exceed 5 MB.'
            )

        try:
            with Image.open(value) as image:
                image_format = image.format
                image.verify()
        except (OSError, ValueError) as exc:
            raise serializers.ValidationError(
                'Upload a valid image.'
            ) from exc
        finally:
            value.seek(0)

        if image_format not in {'JPEG', 'PNG', 'WEBP'}:
            raise serializers.ValidationError(
                'Only JPEG, PNG, and WebP images are supported.'
            )
        return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(read_only=True)

    class Meta:
        model = ProductImage
        fields = ('id', 'image', 'created_at')
        read_only_fields = fields


class ProductGalleryUploadSerializer(serializers.Serializer):
    images = serializers.ListField(
        child=ValidatedProductImageField(),
        allow_empty=False,
        max_length=10,
        write_only=True,
    )

    def create(self, validated_data):
        product = validated_data['product']
        created = []
        try:
            for image in validated_data['images']:
                created.append(
                    ProductImage.objects.create(
                        product=product,
                        image=image,
                    )
                )
        except Exception:
            for product_image in created:
                product_image.image.delete(save=False)
            raise
        return created


class ProductSerializer(serializers.ModelSerializer):
    image = ValidatedProductImageField(required=False, allow_null=True)
    gallery_images = ProductImageSerializer(many=True, read_only=True)
    category_name = serializers.CharField(
        source='category.name',
        read_only=True,
    )
    rating_average = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        read_only=True,
        default=0,
    )
    review_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'slug',
            'description',
            'image',
            'gallery_images',
            'price',
            'stock_quantity',
            'minimum_stock_quantity',
            'is_active',
            'category',
            'category_name',
            'rating_average',
            'review_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class ProductReviewSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    verified_purchase = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = (
            'id', 'rating', 'title', 'comment', 'customer',
            'verified_purchase', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'customer', 'verified_purchase', 'created_at', 'updated_at',
        )

    def get_customer(self, review):
        full_name = review.user.get_full_name().strip()
        return {
            'id': review.user_id,
            'name': full_name or review.user.username,
        }

    def get_verified_purchase(self, review):
        return True

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context['request']
        product = self.context['product']
        if self.instance is None:
            if ProductReview.objects.filter(
                product=product,
                user=request.user,
            ).exists():
                raise serializers.ValidationError({
                    'detail': 'You have already reviewed this product.',
                })
            purchased = OrderItem.objects.filter(
                product=product,
                order__user=request.user,
                order__payment_status='paid',
            ).exists()
            if not purchased:
                raise serializers.ValidationError({
                    'detail': 'Only customers with a paid purchase may review this product.',
                })
        return attrs
