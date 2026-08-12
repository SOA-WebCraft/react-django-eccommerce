from PIL import Image
from rest_framework import serializers

from .models import Category, Product, ProductImage


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
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
