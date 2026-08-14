import hashlib
import hmac
import json
import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from invoices.services import create_invoice, generate_invoice_pdf

from .emails import send_order_confirmation, send_order_status_email
from .models import (
    CheckoutAttempt,
    Coupon,
    GiftCard,
    GiftCardTransaction,
    Order,
    OrderTimelineEvent,
    PaymentTransaction,
    Promotion,
    RefundRequest,
    ReturnRequest,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
    StoreConfiguration,
)
from .analytics import build_analytics_snapshot
from .serializers import (
    CheckoutSessionSerializer,
    CouponManagementSerializer,
    GiftCardSerializer,
    GiftCardTransactionSerializer,
    HostedPaymentSerializer,
    PaymentTransactionSerializer,
    PromotionSerializer,
    CheckoutStatusSerializer,
    OrderSerializer,
    OrderStatusUpdateSerializer,
    RefundRequestSerializer,
    ReturnRequestSerializer,
    StaffRefundRequestSerializer,
    StaffReturnRequestSerializer,
    StaffReturnUpdateSerializer,
    StaffOrderSerializer,
    ShippingMethodSerializer,
    ShippingRateSerializer,
    ShippingZoneSerializer,
    StoreConfigurationSerializer,
    QuoteSerializer,
)
from .services import (
    create_checkout_session,
    create_hosted_payment,
    available_payment_methods,
    _paypal_access_token,
    _request_json,
    fulfill_checkout,
    release_checkout_coupon,
    process_full_refund,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class CanManageStoreSettings(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and request.user.is_active
            and (
                request.user.is_superuser
                or request.user.has_perm('orders.manage_store_settings')
            )
        )


class StaffStoreConfigurationView(APIView):
    permission_classes = (CanManageStoreSettings,)
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def get(self, request):
        return Response(StoreConfigurationSerializer(
            StoreConfiguration.load(), context={'request': request},
        ).data)

    def patch(self, request):
        serializer = StoreConfigurationSerializer(
            StoreConfiguration.load(), data=request.data, partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class StaffSystemSettingsView(APIView):
    permission_classes = (CanManageStoreSettings,)

    def get(self, request):
        validators = [
            item['NAME'].rsplit('.', 1)[-1]
            for item in settings.AUTH_PASSWORD_VALIDATORS
        ]
        return Response({
            'can_manage_users': request.user.is_superuser,
            'store_currency': settings.STORE_CURRENCY,
            'payments': [
                {
                    'provider': item['provider'],
                    'label': item['label'],
                    'configured': item['enabled'],
                }
                for item in available_payment_methods()
                if item['provider'] != 'store_credit'
            ],
            'email': {
                'backend': settings.EMAIL_BACKEND.rsplit('.', 1)[-1],
                'host': settings.EMAIL_HOST,
                'port': settings.EMAIL_PORT,
                'tls': settings.EMAIL_USE_TLS,
                'configured': bool(settings.EMAIL_HOST_USER),
            },
            'security': {
                'password_validators': validators,
                'session_timeout_seconds': settings.SESSION_COOKIE_AGE,
                'two_factor_authentication': False,
                'login_history': False,
                'api_keys': False,
            },
            'integrations': {
                'shipping_providers': False,
                'accounting': False,
                'marketing': False,
                'sms': False,
                'push': False,
                'backup_restore': False,
            },
        })


def _complete_paid_checkout(
    checkout_id, payment_intent, provider='stripe', method=None, card_brand='',
):
    attempt, refund_needed = fulfill_checkout(
        checkout_id, payment_intent, provider, method, card_brand,
    )
    if refund_needed and provider == 'stripe':
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            stripe.Refund.create(
                payment_intent=attempt.stripe_payment_intent,
                reason='requested_by_customer',
                idempotency_key=f'stock-refund-{attempt.pk}',
            )
            attempt.status = CheckoutAttempt.Status.REFUNDED
            release_checkout_coupon(attempt)
        except stripe.StripeError:
            attempt.status = CheckoutAttempt.Status.REFUND_FAILED
        attempt.save(update_fields=('status', 'updated_at'))
    elif attempt.order_id:
        invoice = create_invoice(attempt.order)
        if not invoice.pdf_file:
            try:
                generate_invoice_pdf(invoice)
            except (ImportError, OSError, RuntimeError):
                logger.exception(
                    'Invoice PDF generation failed for %s.',
                    invoice.pk,
                )
        send_order_confirmation(attempt.order_id)
    return attempt


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return StaffOrderSerializer
        return OrderSerializer

    def get_queryset(self):
        queryset = Order.objects.prefetch_related(
            'items', 'timeline_events__created_by'
        ).select_related(
            'invoice',
            'user',
            'payment_transaction',
            'return_request',
            'refund_request',
        )
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        order_status = self.request.query_params.get('status')
        if order_status:
            valid = {choice for choice, _ in Order.Status.choices}
            if order_status not in valid:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'status': 'Must be a valid order status.'})
            queryset = queryset.filter(status=order_status)
        return queryset


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.request.user.is_staff:
            return StaffOrderSerializer
        return OrderSerializer

    def get_queryset(self):
        queryset = Order.objects.prefetch_related(
            'items', 'timeline_events__created_by'
        ).select_related(
            'invoice',
            'user',
            'payment_transaction',
            'return_request',
            'refund_request',
        )
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset

    def patch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied('Staff access is required.')
        with transaction.atomic():
            order = get_object_or_404(
                self.get_queryset().select_for_update(),
                pk=kwargs['pk'],
            )
            serializer = OrderStatusUpdateSerializer(
                order,
                data=request.data,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            order = serializer.save()
        return Response(
            StaffOrderSerializer(
                order,
                context=self.get_serializer_context(),
            ).data
        )


class CustomerReturnRequestView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        if order.status != Order.Status.COMPLETED:
            return Response(
                {'order': 'Returns can be requested only after delivery.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.payment_status != 'paid':
            return Response(
                {'payment': 'This order is not eligible for a return.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ReturnRequest.objects.filter(order=order).exists():
            return Response(
                {'order': 'A return request already exists for this order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ReturnRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return_request = serializer.save(order=order)
        OrderTimelineEvent.objects.create(
            order=order,
            event_type='return_requested',
            description='Customer submitted a return request.',
        )
        return Response(
            ReturnRequestSerializer(return_request).data,
            status=status.HTTP_201_CREATED,
        )


class StaffReturnListView(generics.ListAPIView):
    serializer_class = StaffReturnRequestSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        queryset = ReturnRequest.objects.select_related('order__user')
        return_status = self.request.query_params.get('status')
        if return_status:
            if return_status not in ReturnRequest.Status.values:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'status': 'Invalid return status.'})
            queryset = queryset.filter(status=return_status)
        return queryset


class StaffReturnDetailView(generics.RetrieveAPIView):
    serializer_class = StaffReturnRequestSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = ReturnRequest.objects.select_related('order__user')

    def patch(self, request, *args, **kwargs):
        with transaction.atomic():
            return_request = get_object_or_404(
                self.get_queryset().select_for_update(), pk=kwargs['pk']
            )
            serializer = StaffReturnUpdateSerializer(
                return_request, data=request.data, partial=True,
            )
            serializer.is_valid(raise_exception=True)
            return_request = serializer.save(resolved_by=request.user)
            OrderTimelineEvent.objects.create(
                order=return_request.order,
                event_type='return_updated',
                description=(
                    f'Return request changed to '
                    f'{return_request.get_status_display()}.'
                ),
                created_by=request.user,
            )
        return Response(StaffReturnRequestSerializer(return_request).data)


class StaffRefundListView(generics.ListAPIView):
    serializer_class = StaffRefundRequestSerializer
    permission_classes = (permissions.IsAdminUser,)
    queryset = RefundRequest.objects.select_related('order__user')


class StaffOrderRefundView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, pk):
        get_object_or_404(Order, pk=pk)
        refund = process_full_refund(pk, request.user)
        return Response(RefundRequestSerializer(refund).data)


class StaffOrderEmailView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if not send_order_status_email(order.pk):
            return Response(
                {'email': 'The order email could not be delivered.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        OrderTimelineEvent.objects.create(
            order=order,
            event_type='email_sent',
            description='Order status email sent to the customer.',
            created_by=request.user,
        )
        return Response({'detail': 'Order status email sent.'})


class StaffAnalyticsView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request):
        return Response(build_analytics_snapshot())


class StaffAnalyticsSocketTicketView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request):
        from django.core import signing

        from .consumers import ANALYTICS_TICKET_SALT

        ticket = signing.dumps(
            {'user_id': request.user.pk},
            salt=ANALYTICS_TICKET_SALT,
            compress=True,
        )
        path = '/ws/staff/analytics/'
        base_url = settings.ANALYTICS_WEBSOCKET_BASE_URL
        return Response({
            'ticket': ticket,
            'websocket_url': f'{base_url}{path}' if base_url else path,
            'expires_in': settings.ANALYTICS_WEBSOCKET_TICKET_MAX_AGE,
        })


class PaymentMethodListView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response({'results': [
            item for item in available_payment_methods() if item['enabled']
        ]})


class StaffPaymentTransactionListView(generics.ListAPIView):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = PaymentTransactionSerializer

    def get_queryset(self):
        queryset = PaymentTransaction.objects.select_related('order')
        for field in ('provider', 'method', 'status'):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        for field, lookup in (('date_from', 'created_at__date__gte'), ('date_to', 'created_at__date__lte')):
            raw = self.request.query_params.get(field)
            if raw:
                value = parse_date(raw)
                if value is None:
                    raise ValidationError({field: 'Use an ISO date in YYYY-MM-DD format.'})
                queryset = queryset.filter(**{lookup: value})
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(provider_reference__icontains=search)
                | Q(order__order_number__icontains=search)
            )
        return queryset


class StaffPaymentMethodView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request):
        counts = {
            (row['provider'], row['method']): row['count']
            for row in PaymentTransaction.objects.values('provider', 'method').annotate(count=Count('id'))
        }
        return Response({'results': [
            {**item, 'transactions': counts.get((item['provider'], item['method']), 0)}
            for item in available_payment_methods()
        ]})


class StaffPaymentReportView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request):
        queryset = PaymentTransaction.objects.all()
        for field, lookup in (('date_from', 'created_at__date__gte'), ('date_to', 'created_at__date__lte')):
            raw = request.query_params.get(field)
            if raw:
                value = parse_date(raw)
                if value is None:
                    raise ValidationError({field: 'Use an ISO date in YYYY-MM-DD format.'})
                queryset = queryset.filter(**{lookup: value})
        rows = []
        currencies = queryset.values('store_currency').distinct()
        for currency_row in currencies:
            currency = currency_row['store_currency']
            currency_transactions = queryset.filter(store_currency=currency)
            paid = currency_transactions.filter(status__in=('paid', 'refunded'))
            gross = paid.aggregate(value=Sum('store_amount', default=Decimal('0.00')))['value']
            refunded = currency_transactions.aggregate(value=Sum('refunded_amount', default=Decimal('0.00')))['value']
            rows.append({
                'currency': currency, 'gross_revenue': gross,
                'refunded_amount': refunded, 'net_revenue': gross - refunded,
                'paid_transactions': paid.count(),
                'transactions': currency_transactions.count(),
            })
        providers = list(queryset.values('provider').annotate(
            transactions=Count('id'),
            paid=Count('id', filter=Q(status__in=('paid', 'refunded'))),
        ).order_by('provider'))
        return Response({'currencies': rows, 'providers': providers})


class StaffShippingOrderListView(generics.ListAPIView):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = StaffOrderSerializer

    def get_queryset(self):
        queryset = Order.objects.filter(
            status__in=(Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.COMPLETED),
        ).select_related('user', 'invoice', 'return_request').prefetch_related(
            'items', 'timeline_events__created_by',
        )
        order_status = self.request.query_params.get('status')
        if order_status:
            allowed = {Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.COMPLETED}
            if order_status not in allowed:
                raise ValidationError({'status': 'Use processing, shipped, or delivered.'})
            queryset = queryset.filter(status=order_status)
        return queryset


class StaffShippingMethodViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')


class StaffShippingZoneViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = ShippingZoneSerializer
    queryset = ShippingZone.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')


class StaffShippingRateViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = ShippingRateSerializer
    queryset = ShippingRate.objects.select_related('method', 'zone')
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')


class StaffCouponViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = CouponManagementSerializer
    queryset = Coupon.objects.all().order_by('-is_active', 'code')
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')


class StaffPromotionViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = PromotionSerializer
    queryset = Promotion.objects.prefetch_related('categories', 'products')
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')


class StaffGiftCardViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = GiftCardSerializer
    queryset = GiftCard.objects.select_related('created_by')
    http_method_names = ('get', 'post', 'patch', 'head', 'options')


class StaffGiftCardTransactionListView(generics.ListAPIView):
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = GiftCardTransactionSerializer

    def get_queryset(self):
        get_object_or_404(GiftCard, pk=self.kwargs['pk'])
        return GiftCardTransaction.objects.filter(
            gift_card_id=self.kwargs['pk'],
        ).select_related('order')


class HostedPaymentView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = HostedPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt, checkout_url, provider, method = create_hosted_payment(
            request.user, dict(serializer.validated_data),
        )
        return Response({
            'id': attempt.pk, 'checkout_url': checkout_url,
            'provider': provider, 'method': method,
        }, status=status.HTTP_201_CREATED)


class CheckoutQuoteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = QuoteSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        totals = serializer.save()
        return Response({
            key: value
            for key, value in totals.items()
            if key not in {'coupon', 'gift_card'}
        })


class CheckoutSessionView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = CheckoutSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt, checkout_url = create_checkout_session(
            request.user,
            serializer.validated_data,
        )
        return Response(
            {'id': attempt.pk, 'checkout_url': checkout_url},
            status=status.HTTP_201_CREATED,
        )


class CheckoutStatusView(generics.RetrieveAPIView):
    serializer_class = CheckoutStatusSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return (
            CheckoutAttempt.objects.filter(user=self.request.user)
            .select_related('order__invoice')
        )

    def retrieve(self, request, *args, **kwargs):
        attempt = self.get_object()
        if (
            attempt.status == CheckoutAttempt.Status.CREATED
            and attempt.stripe_session_id
            and settings.STRIPE_SECRET_KEY
        ):
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                session = stripe.checkout.Session.retrieve(
                    attempt.stripe_session_id,
                )
            except stripe.StripeError:
                logger.warning(
                    'Unable to reconcile Stripe session %s.',
                    attempt.stripe_session_id,
                    exc_info=True,
                )
            else:
                if session.get('payment_status') == 'paid':
                    attempt = _complete_paid_checkout(
                        attempt.pk,
                        session.get('payment_intent', ''),
                    )
                    attempt = self.get_queryset().get(pk=attempt.pk)
        elif attempt.status == CheckoutAttempt.Status.CREATED:
            try:
                payment = attempt.transaction
            except PaymentTransaction.DoesNotExist:
                payment = None
            if payment and payment.provider == PaymentTransaction.Provider.PAYSTACK:
                try:
                    result = _request_json(
                        f'https://api.paystack.co/transaction/verify/{payment.provider_reference}',
                        headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
                    )['data']
                    if (
                        result.get('status') == 'success'
                        and result.get('currency') == payment.provider_currency
                        and Decimal(str(result.get('amount', 0))) == payment.provider_amount * 100
                    ):
                        _complete_paid_checkout(
                            attempt.pk, payment.provider_reference, 'paystack',
                            payment.method, result.get('authorization', {}).get('brand', ''),
                        )
                        attempt = self.get_queryset().get(pk=attempt.pk)
                except Exception:
                    logger.warning('Unable to reconcile Paystack checkout.', exc_info=True)
            elif payment and payment.provider == PaymentTransaction.Provider.PAYPAL:
                try:
                    result = _request_json(
                        f'{settings.PAYPAL_API_BASE}/v2/checkout/orders/{payment.provider_reference}/capture',
                        method='POST', headers={'Authorization': f'Bearer {_paypal_access_token()}',
                                                'PayPal-Request-Id': f'capture-{attempt.pk}'}, data={},
                    )
                    capture = result['purchase_units'][0]['payments']['captures'][0]
                    amount = capture['amount']
                    if (
                        capture['status'] == 'COMPLETED'
                        and amount['currency_code'] == payment.provider_currency
                        and Decimal(amount['value']) == payment.provider_amount
                    ):
                        _complete_paid_checkout(
                            attempt.pk, capture['id'], 'paypal', 'paypal',
                        )
                        attempt = self.get_queryset().get(pk=attempt.pk)
                except Exception:
                    logger.info('PayPal checkout is not ready for capture.', exc_info=True)
        serializer = self.get_serializer(attempt)
        return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        try:
            event = stripe.Webhook.construct_event(
                request.body,
                request.META.get('HTTP_STRIPE_SIGNATURE', ''),
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.SignatureVerificationError):
            return Response(
                {'detail': 'Invalid Stripe signature.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        event_type = event['type']
        session = event['data']['object']
        if event_type == 'checkout.session.completed':
            checkout_id = session.get('metadata', {}).get('checkout_id')
            if checkout_id and session.get('payment_status') == 'paid':
                _complete_paid_checkout(
                    checkout_id,
                    session.get('payment_intent', ''),
                )
        elif event_type == 'checkout.session.expired':
            try:
                attempt = CheckoutAttempt.objects.get(
                    stripe_session_id=session.get('id'),
                )
            except CheckoutAttempt.DoesNotExist:
                pass
            else:
                if attempt.status == CheckoutAttempt.Status.CREATED:
                    release_checkout_coupon(attempt)
                    attempt.status = CheckoutAttempt.Status.EXPIRED
                    attempt.save(update_fields=('status', 'updated_at'))
        return HttpResponse(status=200)


@method_decorator(csrf_exempt, name='dispatch')
class PaystackWebhookView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
        expected = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode(), request.body, hashlib.sha512,
        ).hexdigest()
        if not settings.PAYSTACK_SECRET_KEY or not hmac.compare_digest(signature, expected):
            return Response({'detail': 'Invalid Paystack signature.'}, status=400)
        payload = request.data
        if payload.get('event') == 'charge.success':
            data = payload.get('data', {})
            try:
                payment = PaymentTransaction.objects.get(
                    provider='paystack', provider_reference=data.get('reference', ''),
                )
            except PaymentTransaction.DoesNotExist:
                return HttpResponse(status=200)
            try:
                amount = Decimal(str(data.get('amount', '')))
            except (ValueError, TypeError, ArithmeticError):
                amount = Decimal('-1')
            metadata = data.get('metadata') or {}
            if (
                data.get('status') == 'success'
                and data.get('currency') == payment.provider_currency
                and amount == payment.provider_amount * 100
                and str(metadata.get('checkout_id', payment.checkout_id))
                == str(payment.checkout_id)
            ):
                authorization = data.get('authorization') or {}
                _complete_paid_checkout(
                    payment.checkout_id, data.get('reference', ''), 'paystack',
                    payment.method, authorization.get('brand', ''),
                )
        elif payload.get('event') == 'charge.failed':
            data = payload.get('data', {})
            payment = PaymentTransaction.objects.filter(
                provider='paystack', provider_reference=data.get('reference', ''),
            ).select_related('checkout').first()
            if payment and payment.checkout.status == CheckoutAttempt.Status.CREATED:
                release_checkout_coupon(payment.checkout)
                payment.checkout.status = CheckoutAttempt.Status.FAILED
                payment.checkout.save(update_fields=('status', 'updated_at'))
                payment.status = PaymentTransaction.Status.FAILED
                payment.save(update_fields=('status', 'updated_at'))
        return HttpResponse(status=200)


@method_decorator(csrf_exempt, name='dispatch')
class PayPalWebhookView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        if not settings.PAYPAL_WEBHOOK_ID:
            return Response({'detail': 'PayPal webhook is not configured.'}, status=400)
        verification = _request_json(
            f'{settings.PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature',
            method='POST', headers={'Authorization': f'Bearer {_paypal_access_token()}'},
            data={
                'auth_algo': request.META.get('HTTP_PAYPAL_AUTH_ALGO', ''),
                'cert_url': request.META.get('HTTP_PAYPAL_CERT_URL', ''),
                'transmission_id': request.META.get('HTTP_PAYPAL_TRANSMISSION_ID', ''),
                'transmission_sig': request.META.get('HTTP_PAYPAL_TRANSMISSION_SIG', ''),
                'transmission_time': request.META.get('HTTP_PAYPAL_TRANSMISSION_TIME', ''),
                'webhook_id': settings.PAYPAL_WEBHOOK_ID,
                'webhook_event': request.data,
            },
        )
        if verification.get('verification_status') != 'SUCCESS':
            return Response({'detail': 'Invalid PayPal signature.'}, status=400)
        if request.data.get('event_type') == 'PAYMENT.CAPTURE.COMPLETED':
            resource = request.data.get('resource', {})
            custom_id = resource.get('custom_id')
            if custom_id:
                try:
                    payment = PaymentTransaction.objects.get(
                        checkout_id=custom_id, provider='paypal',
                    )
                except (PaymentTransaction.DoesNotExist, ValueError):
                    return HttpResponse(status=200)
                amount = resource.get('amount', {})
                if (
                    amount.get('currency_code') == payment.provider_currency
                    and Decimal(str(amount.get('value', 0))) == payment.provider_amount
                ):
                    _complete_paid_checkout(
                        custom_id, resource.get('id', ''), 'paypal', 'paypal',
                    )
        return HttpResponse(status=200)
