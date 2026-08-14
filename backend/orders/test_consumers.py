from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TransactionTestCase, override_settings

from config.asgi import application

from .consumers import ANALYTICS_TICKET_SALT


User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    ANALYTICS_WEBSOCKET_INTERVAL=60,
)
class StaffAnalyticsConsumerTests(TransactionTestCase):
    def ticket(self, user):
        return signing.dumps(
            {'user_id': user.pk},
            salt=ANALYTICS_TICKET_SALT,
            compress=True,
        )

    def test_staff_ticket_connects_and_receives_snapshot(self):
        staff = User.objects.create_user(
            username='socket-staff',
            password='secret',
            is_staff=True,
        )

        async def exercise_socket():
            communicator = WebsocketCommunicator(
                application,
                f'/ws/staff/analytics/?ticket={self.ticket(staff)}',
                headers=[(b'origin', b'http://testserver')],
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            message = await communicator.receive_json_from(timeout=5)
            self.assertEqual(message['type'], 'analytics.snapshot')
            self.assertIn('summary', message['data'])
            await communicator.disconnect()

        async_to_sync(exercise_socket)()

    def test_nonstaff_ticket_is_rejected(self):
        customer = User.objects.create_user(
            username='socket-customer',
            password='secret',
        )

        async def exercise_socket():
            communicator = WebsocketCommunicator(
                application,
                f'/ws/staff/analytics/?ticket={self.ticket(customer)}',
                headers=[(b'origin', b'http://testserver')],
            )
            connected, close_code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(close_code, 4403)

        async_to_sync(exercise_socket)()
