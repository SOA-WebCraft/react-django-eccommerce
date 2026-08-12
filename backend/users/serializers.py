from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from rest_framework import serializers

from .models import Profile


User = get_user_model()

ALLOWED_ROLE_PERMISSIONS = {
    ('catalog', action)
    for action in (
        'add_category', 'change_category', 'delete_category', 'view_category',
        'add_product', 'change_product', 'delete_product', 'view_product',
    )
} | {
    ('orders', action)
    for action in (
        'view_order', 'change_order', 'view_shippingmethod',
        'add_shippingmethod', 'change_shippingmethod', 'delete_shippingmethod',
        'manage_store_settings',
    )
}


def allowed_permissions():
    query = Q()
    for app_label, codename in ALLOWED_ROLE_PERMISSIONS:
        query |= Q(content_type__app_label=app_label, codename=codename)
    return Permission.objects.filter(query).select_related('content_type')


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        return attrs


class UserSerializer(serializers.ModelSerializer):
    can_manage_orders = serializers.SerializerMethodField()
    can_manage_catalog = serializers.SerializerMethodField()
    can_manage_settings = serializers.SerializerMethodField()
    first_name = serializers.CharField(source='profile.first_name', read_only=True)
    last_name = serializers.CharField(source='profile.last_name', read_only=True)
    phone = serializers.CharField(source='profile.phone', read_only=True)
    address = serializers.CharField(source='profile.address', read_only=True)
    city = serializers.CharField(source='profile.city', read_only=True)
    postal_code = serializers.CharField(source='profile.postal_code', read_only=True)
    country = serializers.CharField(source='profile.country', read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'address',
            'city',
            'postal_code',
            'country',
            'can_manage_orders',
            'can_manage_catalog',
            'can_manage_settings',
        )
        read_only_fields = fields

    def get_can_manage_orders(self, user):
        return bool(user.is_active and user.is_staff)

    def get_can_manage_catalog(self, user):
        return bool(
            user.is_active
            and user.is_staff
            and user.has_perms((
                'catalog.add_product',
                'catalog.change_product',
                'catalog.delete_product',
            ))
        )

    def get_can_manage_settings(self, user):
        return bool(
            user.is_active
            and (
                user.is_superuser
                or user.has_perm('orders.manage_store_settings')
            )
        )


class RoleSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        source='permissions', queryset=Permission.objects.none(), many=True,
        required=False, write_only=True,
    )
    permissions = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Group
        fields = ('id', 'name', 'permission_ids', 'permissions', 'member_count')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permission_ids'].child_relation.queryset = allowed_permissions()

    def get_permissions(self, group):
        return [
            {
                'id': permission.id,
                'name': permission.name,
                'codename': permission.codename,
                'app_label': permission.content_type.app_label,
            }
            for permission in group.permissions.all()
            if (permission.content_type.app_label, permission.codename)
            in ALLOWED_ROLE_PERMISSIONS
        ]


class StaffUserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(source='groups', many=True, read_only=True)
    role_ids = serializers.PrimaryKeyRelatedField(
        source='groups', queryset=Group.objects.all(), many=True,
        required=False, write_only=True,
    )

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'is_active', 'is_superuser',
            'roles', 'role_ids', 'date_joined', 'last_login',
        )
        read_only_fields = ('id', 'is_superuser', 'date_joined', 'last_login')

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError('Email is required.')
        return value

    def validate(self, attrs):
        request = self.context['request']
        if self.instance == request.user and attrs.get('is_active') is False:
            raise serializers.ValidationError({
                'is_active': 'You cannot deactivate your own account.'
            })
        if self.instance == request.user and 'groups' in attrs:
            raise serializers.ValidationError({
                'role_ids': 'You cannot change your own roles.'
            })
        return attrs

    def create(self, validated_data):
        groups = validated_data.pop('groups', [])
        user = User(**validated_data, is_staff=True, is_active=True)
        user.set_unusable_password()
        user.save()
        user.groups.set(groups)
        return user


class StaffCustomerListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    phone = serializers.CharField(source='profile.phone', read_only=True)
    orders = serializers.IntegerField(source='order_count', read_only=True)
    total_spent = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'name', 'email', 'phone', 'orders',
            'total_spent', 'status', 'date_joined',
        )
        read_only_fields = fields

    def get_name(self, user):
        profile = user.profile
        full_name = ' '.join(filter(None, (
            profile.first_name,
            profile.last_name,
        )))
        return full_name or user.username

    def get_status(self, user):
        return 'active' if user.is_active else 'inactive'


class StaffCustomerDetailSerializer(StaffCustomerListSerializer):
    personal_details = serializers.SerializerMethodField()
    order_history = serializers.SerializerMethodField()
    saved_addresses = serializers.SerializerMethodField()

    class Meta(StaffCustomerListSerializer.Meta):
        fields = StaffCustomerListSerializer.Meta.fields + (
            'personal_details',
            'order_history',
            'saved_addresses',
        )
        read_only_fields = fields

    def get_personal_details(self, user):
        profile = user.profile
        return {
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'phone': profile.phone,
            'email': user.email,
        }

    def get_order_history(self, user):
        from orders.models import Order
        from orders.serializers import StaffOrderSerializer

        orders = (
            Order.objects.filter(user=user)
            .select_related('user', 'invoice')
            .prefetch_related('items')[:20]
        )
        return StaffOrderSerializer(
            orders,
            many=True,
            context=self.context,
        ).data

    def get_saved_addresses(self, user):
        profile = user.profile
        if not any((
            profile.address,
            profile.city,
            profile.postal_code,
            profile.country,
        )):
            return []
        return [{
            'address': profile.address,
            'city': profile.city,
            'postal_code': profile.postal_code,
            'country': profile.country,
        }]


class ProfileUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=False)
    first_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=32)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=120)
    postal_code = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=40)
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=120)
    current_password = serializers.CharField(required=False, write_only=True, trim_whitespace=False)

    profile_fields = (
        'first_name',
        'last_name',
        'phone',
        'address',
        'city',
        'postal_code',
        'country',
    )

    def validate(self, attrs):
        allowed = {'email', 'current_password', *self.profile_fields}
        unexpected = set(self.initial_data) - allowed
        if unexpected:
            raise serializers.ValidationError({
                field: 'This field cannot be updated.'
                for field in sorted(unexpected)
            })
        email = attrs.get('email')
        if email is not None and email.casefold() != self.instance.email.casefold():
            password = attrs.get('current_password', '')
            if not self.instance.check_password(password):
                raise serializers.ValidationError({
                    'current_password': 'Enter your current password to change email.'
                })
        for field in self.profile_fields:
            if attrs.get(field) == '':
                attrs[field] = None
        return attrs

    def update(self, user, validated_data):
        validated_data.pop('current_password', None)
        if 'email' in validated_data:
            user.email = validated_data.pop('email')
            user.save(update_fields=('email',))
        profile, _ = Profile.objects.get_or_create(user=user)
        changed = []
        for field in self.profile_fields:
            if field in validated_data:
                setattr(profile, field, validated_data[field])
                changed.append(field)
        if changed:
            profile.save(update_fields=(*changed, 'updated_at'))
        user.profile = profile
        return user


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        read_only_fields = ('id',)

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
