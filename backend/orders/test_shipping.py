from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Order, ShippingMethod, ShippingRate, ShippingZone


class StaffShippingApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user('shippingstaff', password='safe-password', is_staff=True)
        self.customer = User.objects.create_user('shippingbuyer', password='safe-password')

    def test_staff_manages_methods_zones_and_rates(self):
        self.client.force_login(self.staff)
        method_response = self.client.post(reverse('staff-shipping-method-list'), {
            'name': 'Express', 'code': 'express', 'kind': 'express',
            'estimated_days': 1, 'is_active': True,
        }, content_type='application/json')
        self.assertEqual(method_response.status_code, 201)
        zone_response = self.client.post(reverse('staff-shipping-zone-list'), {
            'name': 'Greater Accra', 'countries': ['Ghana'],
            'regions': ['Greater Accra'], 'cities': ['Accra'], 'is_active': True,
        }, content_type='application/json')
        self.assertEqual(zone_response.status_code, 201)
        rate_response = self.client.post(reverse('staff-shipping-rate-list'), {
            'method': method_response.data['id'], 'zone': zone_response.data['id'],
            'amount': '25.00', 'free_shipping_threshold': '500.00', 'is_active': True,
        }, content_type='application/json')
        self.assertEqual(rate_response.status_code, 201)
        self.assertEqual(ShippingRate.objects.count(), 1)

    def test_shipping_orders_include_processing_shipped_and_delivered(self):
        Order.objects.create(user=self.customer, status='processing', total='10.00')
        Order.objects.create(user=self.customer, status='cancelled', total='10.00')
        self.client.force_login(self.staff)
        response = self.client.get(reverse('staff-shipping-orders'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_non_staff_cannot_access_shipping_management(self):
        self.client.force_login(self.customer)
        for name in ('staff-shipping-orders', 'staff-shipping-method-list', 'staff-shipping-zone-list', 'staff-shipping-rate-list'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_zone_requires_lists_of_nonblank_names(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('staff-shipping-zone-list'), {
            'name': 'Invalid', 'countries': [''], 'regions': [], 'cities': [],
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('countries', response.data)
