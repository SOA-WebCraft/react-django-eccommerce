import asyncio
import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from .analytics import build_analytics_snapshot


User = get_user_model()
ANALYTICS_TICKET_SALT = 'orders.analytics.websocket'


@database_sync_to_async
def user_from_ticket(ticket):
    try:
        payload = signing.loads(
            ticket,
            salt=ANALYTICS_TICKET_SALT,
            max_age=settings.ANALYTICS_WEBSOCKET_TICKET_MAX_AGE,
        )
        return User.objects.get(
            pk=payload['user_id'],
            is_active=True,
            is_staff=True,
        )
    except (KeyError, signing.BadSignature, User.DoesNotExist):
        return None


class StaffAnalyticsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated or not user.is_staff:
            query = parse_qs(
                self.scope.get('query_string', b'').decode('utf-8')
            )
            ticket = query.get('ticket', [''])[0]
            user = await user_from_ticket(ticket)
        if not user:
            await self.close(code=4403)
            return
        self.scope['user'] = user
        await self.accept()
        self.stream_task = asyncio.create_task(self.stream_snapshots())

    async def disconnect(self, close_code):
        task = getattr(self, 'stream_task', None)
        if task:
            task.cancel()

    async def stream_snapshots(self):
        try:
            while True:
                snapshot = await database_sync_to_async(
                    build_analytics_snapshot
                )()
                await self.send_json({
                    'type': 'analytics.snapshot',
                    'data': snapshot,
                    'sent_at': timezone.now().isoformat(),
                })
                await asyncio.sleep(settings.ANALYTICS_WEBSOCKET_INTERVAL)
        except asyncio.CancelledError:
            return

    @classmethod
    async def encode_json(cls, content):
        return json.dumps(content, cls=DjangoJSONEncoder)
