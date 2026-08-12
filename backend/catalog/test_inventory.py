from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import CheckoutAttempt, CheckoutItem

from .models import Product, PurchaseOrder, StockMovement, Supplier, Category


User = get_user_model()


class InventoryApiTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='inventory-staff', password='secret', is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='customer', password='secret',
        )
        category = Category.objects.create(name='Phones', slug='phones')
        self.product = Product.objects.create(
            category=category,
            name='Store Phone',
            slug='store-phone',
            price=Decimal('100.00'),
            stock_quantity=10,
            minimum_stock_quantity=4,
        )
        self.client.force_authenticate(self.staff)

    def test_stock_levels_include_active_checkout_reservations(self):
        checkout = CheckoutAttempt.objects.create(
            user=self.customer,
            subtotal=Decimal('300.00'),
            total=Decimal('300.00'),
        )
        CheckoutItem.objects.create(
            checkout=checkout,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('100.00'),
            quantity=3,
            line_total=Decimal('300.00'),
        )
        response = self.client.get(reverse('inventory-stock'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stock = response.data['results'][0]
        self.assertEqual(stock['stock_quantity'], 10)
        self.assertEqual(stock['reserved_stock'], 3)
        self.assertEqual(stock['available_stock'], 7)
        self.assertEqual(stock['stock_state'], 'in_stock')

    def test_adjustments_validate_stock_and_create_history(self):
        response = self.client.post(
            reverse('stock-adjustment'),
            {
                'product': self.product.pk,
                'operation': 'remove',
                'quantity': 4,
                'note': 'Damaged items',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        movement = StockMovement.objects.get()
        self.assertEqual(movement.quantity_change, -4)
        self.assertEqual(movement.resulting_stock, 6)
        rejected = self.client.post(
            reverse('stock-adjustment'),
            {'product': self.product.pk, 'operation': 'remove', 'quantity': 7},
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)

    def test_purchase_order_receipt_adds_stock_once(self):
        supplier = Supplier.objects.create(
            name='Phone Supplier', email='supplier@example.com',
        )
        created = self.client.post(
            reverse('purchase-order-list'),
            {
                'supplier': supplier.pk,
                'notes': 'Restock',
                'items': [{
                    'product': self.product.pk,
                    'quantity': 5,
                    'unit_cost': '80.00',
                }],
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        order_id = created.data['id']
        received = self.client.post(
            reverse('purchase-order-receive', args=(order_id,)),
            {},
            format='json',
        )
        self.assertEqual(received.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 15)
        self.assertEqual(received.data['status'], PurchaseOrder.Status.RECEIVED)
        duplicate = self.client.post(
            reverse('purchase-order-receive', args=(order_id,)),
            {},
            format='json',
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 15)

    def test_inventory_requires_staff(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(
            self.client.get(reverse('inventory-stock')).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(reverse('inventory-stock')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        for model in (Supplier, PurchaseOrder, StockMovement):
            self.assertIn(model, admin.site._registry)
