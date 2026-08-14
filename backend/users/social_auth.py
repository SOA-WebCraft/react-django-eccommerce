import json
import re
import time
from urllib.parse import urlencode

from authlib.integrations.django_client import OAuth
from joserfc import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from .models import Profile, SocialIdentity


PROVIDERS = {
    'google': {
        'label': 'Google',
        'metadata': 'https://accounts.google.com/.well-known/openid-configuration',
        'scope': 'openid email profile',
    },
    'apple': {
        'label': 'Apple',
        'metadata': 'https://appleid.apple.com/.well-known/openid-configuration',
        'scope': 'openid email name',
    },
    'facebook': {
        'label': 'Facebook',
        'authorize_url': 'https://www.facebook.com/v23.0/dialog/oauth',
        'access_token_url': 'https://graph.facebook.com/v23.0/oauth/access_token',
        'userinfo_url': 'https://graph.facebook.com/me?fields=id,name,email,first_name,last_name',
        'scope': 'email,public_profile',
    },
    'linkedin': {
        'label': 'LinkedIn',
        'metadata': 'https://www.linkedin.com/oauth/.well-known/openid-configuration',
        'scope': 'openid profile email',
    },
}


class SocialAuthError(Exception):
    pass


def provider_is_configured(provider):
    config = settings.SOCIAL_AUTH.get(provider, {})
    required = ('client_id', 'client_secret')
    if provider == 'apple':
        required = ('client_id', 'team_id', 'key_id', 'private_key')
    return all(config.get(key) for key in required)


def provider_list():
    return [
        {
            'provider': key,
            'label': config['label'],
            'enabled': provider_is_configured(key),
        }
        for key, config in PROVIDERS.items()
    ]


def _apple_client_secret(config):
    now = int(time.time())
    header = {'alg': 'ES256', 'kid': config['key_id']}
    payload = {
        'iss': config['team_id'],
        'iat': now,
        'exp': now + 3600,
        'aud': 'https://appleid.apple.com',
        'sub': config['client_id'],
    }
    private_key = config['private_key'].replace('\\n', '\n')
    value = jwt.encode(header, payload, private_key)
    return value.tokens()


def oauth_client(provider):
    definition = PROVIDERS[provider]
    config = settings.SOCIAL_AUTH[provider]
    client_secret = (
        _apple_client_secret(config)
        if provider == 'apple'
        else config['client_secret']
    )
    oauth = OAuth()
    registration = {
        'client_id': config['client_id'],
        'client_secret': client_secret,
        'client_kwargs': {'scope': definition['scope']},
    }
    if 'metadata' in definition:
        registration['server_metadata_url'] = definition['metadata']
    else:
        registration.update({
            'authorize_url': definition['authorize_url'],
            'access_token_url': definition['access_token_url'],
            'api_base_url': 'https://graph.facebook.com/',
        })
    oauth.register(provider, **registration)
    return oauth.create_client(provider)


def callback_url(provider):
    path = reverse('user-social-callback', kwargs={'provider': provider})
    return f'{settings.FRONTEND_BASE_URL}{path}'


def safe_destination(value):
    if isinstance(value, str) and value.startswith('/') and not value.startswith('//'):
        return value
    return '/account'


def profile_from_token(provider, client, token):
    if provider == 'facebook':
        response = client.get(PROVIDERS[provider]['userinfo_url'], token=token)
        response.raise_for_status()
        data = response.json()
        data['sub'] = data.get('id')
        data['email_verified'] = bool(data.get('email'))
        return data
    data = token.get('userinfo')
    if not data:
        data = client.parse_id_token(token)
    return dict(data or {})


def _unique_username(profile):
    User = get_user_model()
    base = profile.get('preferred_username') or profile['email'].split('@')[0]
    base = re.sub(r'[^\w.@+-]', '', base)[:130] or 'customer'
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f'{base[:140 - len(str(suffix))]}-{suffix}'
    return candidate


@transaction.atomic
def login_or_create_social_user(provider, profile):
    subject = str(profile.get('sub') or '')
    email = str(profile.get('email') or '').strip().lower()
    email_verified = profile.get('email_verified', True)
    if not subject:
        raise SocialAuthError('The provider did not return an account identifier.')
    if not email or email_verified in (False, 'false', '0'):
        raise SocialAuthError('A verified email address is required.')

    identity = SocialIdentity.objects.select_related('user').filter(
        provider=provider,
        subject=subject,
    ).first()
    if identity:
        if not identity.user.is_active:
            raise SocialAuthError('This account is inactive.')
        return identity.user

    User = get_user_model()
    matches = list(User.objects.filter(email__iexact=email, is_active=True)[:2])
    if len(matches) > 1:
        raise SocialAuthError('This email matches multiple accounts. Contact support for assistance.')
    if matches:
        user = matches[0]
    else:
        user = User(username=_unique_username({'email': email, **profile}), email=email)
        user.set_unusable_password()
        user.save()

    SocialIdentity.objects.create(
        user=user,
        provider=provider,
        subject=subject,
        email=email,
    )
    profile_record, _ = Profile.objects.get_or_create(user=user)
    first_name = profile.get('given_name') or profile.get('first_name')
    last_name = profile.get('family_name') or profile.get('last_name')
    changed = []
    if first_name and not profile_record.first_name:
        profile_record.first_name = first_name
        changed.append('first_name')
    if last_name and not profile_record.last_name:
        profile_record.last_name = last_name
        changed.append('last_name')
    if changed:
        profile_record.save(update_fields=changed + ['updated_at'])
        if 'profile' in user._state.fields_cache:
            user._state.fields_cache['profile'] = profile_record
    return user


def frontend_result_url(success, destination='/', message=''):
    query = {'status': 'success' if success else 'error'}
    if success:
        query['next'] = safe_destination(destination)
    else:
        query['message'] = message or 'Social sign-in could not be completed.'
    return f'{settings.FRONTEND_BASE_URL}/auth/social/callback?{urlencode(query)}'


def apple_name(request):
    raw = request.POST.get('user')
    if not raw:
        return {}
    try:
        return json.loads(raw).get('name', {})
    except (TypeError, ValueError):
        return {}
