import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


logger = logging.getLogger(__name__)
User = get_user_model()


def send_password_reset_emails(email):
    users = User.objects.filter(email__iexact=email, is_active=True)
    for user in users.iterator():
        if not user.has_usable_password():
            continue
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f'{settings.FRONTEND_BASE_URL}/reset-password/{uid}/{token}'
        message = (
            f'Hello {user.get_username()},\n\n'
            'Use the link below to reset your ECCO password. This link expires '
            'in one hour and can be used only once.\n\n'
            f'{reset_url}\n\n'
            'If you did not request this reset, you can ignore this email.'
        )
        try:
            send_mail(
                'Reset your ECCO password',
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                'Password reset email delivery failed for user %s.',
                user.pk,
            )


def send_staff_invitation(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f'{settings.FRONTEND_BASE_URL}/reset-password/{uid}/{token}'
    try:
        send_mail(
            'Set up your ECCO staff account',
            (
                f'Hello {user.get_username()},\n\n'
                'A staff account has been created for you. Use this one-time '
                f'link to set your password:\n\n{reset_url}\n\n'
                'If you were not expecting this invitation, ignore this email.'
            ),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('Staff invitation delivery failed for user %s.', user.pk)
        return False
