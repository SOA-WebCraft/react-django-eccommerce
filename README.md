# Minimal Ecommerce API

A small REST API built with Django, Django REST Framework, secure server-side
session authentication, and SQLite for local development.

## Local setup

Run these commands from the repository root in Windows PowerShell. Django and
all backend-owned files, including the Python virtual environment, live in
`backend/`.

Create and activate a virtual environment:

```powershell
py -m venv backend\venv
.\backend\venv\Scripts\Activate.ps1
```

Install the pinned dependencies:

```powershell
python -m pip install -r backend/requirements.txt
```

Create the ignored local settings file from the safe template:

```powershell
Copy-Item backend/.env.example backend/.env
```

Values in `backend/.env` are loaded automatically for local development. Existing
PowerShell, service, or hosting environment variables take precedence.

Apply the database migrations:

```powershell
python backend/manage.py migrate
```

Populate the local catalog with the standard electronics sample data:

```powershell
python backend/manage.py seed_catalog
```

The command is safe to rerun. It creates missing categories and products without
overwriting later staff edits.

To intentionally restore the curated descriptions for seeded products without
changing their prices, stock, images, categories, or active status, run:

```powershell
python backend/manage.py seed_catalog --refresh-descriptions
```

Create a staff administrator:

```powershell
python backend/manage.py createsuperuser
```

The `Catalog Managers` group is created automatically by `migrate`; assign it
to staff who should manage categories, products, and product images without
granting broader permissions.

Start the local development server:

```powershell
python backend/manage.py runserver
```

The API is then available under `http://127.0.0.1:8000/api/`, and Django admin
is available at `http://127.0.0.1:8000/admin/`.

## Live Gmail transactional email

Password-reset and successful-purchase confirmation emails use Gmail SMTP locally
and in deployed environments. First
enable 2-Step Verification on the sending Google account, then create a Google
app password. Use that 16-character app password; never use the normal Google
account password.

Enter the following values directly in the ignored `backend/.env` file:

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-address@gmail.com
EMAIL_HOST_PASSWORD=your-google-app-password
DEFAULT_FROM_EMAIL="ECCO Store <${EMAIL_HOST_USER}>"
FRONTEND_BASE_URL=http://127.0.0.1:5173
PASSWORD_RESET_TIMEOUT_SECONDS=3600
```

Remove spaces from the app password when pasting it. Restart Django after every
`.env` change. Process or hosting environment variables still take precedence.
Never commit the Gmail address or app password to `.env.example` or source
control.

Check configuration without printing either credential:

```powershell
python backend/manage.py shell -c "from django.conf import settings; print('Gmail SMTP:', settings.EMAIL_BACKEND.endswith('smtp.EmailBackend') and settings.EMAIL_HOST == 'smtp.gmail.com'); print('Credentials configured:', bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)); print('Reset URL configured:', settings.FRONTEND_BASE_URL == 'http://127.0.0.1:5173')"
```

After both credentials are configured, send one test message to the same Gmail
account:

```powershell
python backend/manage.py shell -c "from django.conf import settings; from django.core.mail import send_mail; print('Messages sent:', send_mail('ECCO email test', 'Gmail SMTP is configured correctly.', settings.DEFAULT_FROM_EMAIL, [settings.EMAIL_HOST_USER]))"
```

Google SMTP errors `534` and `535` usually mean 2-Step Verification is disabled,
the app password is incorrect, or a normal account password was used. Connection
timeouts usually mean outbound TCP port 587 is blocked. Reset links expire after
one hour and can be used once.

Uploaded product images are stored under `backend/media/product_images/`. In local
development Django serves them from `http://127.0.0.1:8000/media/`. JPEG, PNG,
and WebP files up to 5 MB are accepted. Each product may also have up to 10
gallery images, uploaded by staff through `/api/products/{id}/images/`.

Run the complete test suite:

```powershell
Push-Location backend
.\venv\Scripts\python.exe manage.py test
Pop-Location
```

See [api_docs.md](backend/api_docs.md) for the endpoint contract and examples.

## Frontend setup

The React, JavaScript, and Vite storefront lives in `frontend/`. Keep the
Django development server running in one PowerShell window, then open another:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api/` and `/media/` requests to
the Django server at `http://127.0.0.1:8000`, so no local CORS configuration is
required.

The available frontend environment variable is:

```text
VITE_API_BASE_URL=/api
VITE_DEV_PROXY_TARGET=http://127.0.0.1:8000
```

Keep the default relative value for local development and same-site
deployments. The application intentionally uses `SameSite=Lax` cookies and
does not support a cross-site frontend/API deployment.

Django trusts `http://localhost:5173` and `http://127.0.0.1:5173` for CSRF
during local development. If the frontend uses another origin, configure a
comma-separated list before starting Django:

```powershell
$env:DJANGO_CSRF_TRUSTED_ORIGINS="http://localhost:4173"
python backend/manage.py runserver
```

In production, set this variable to the HTTPS application origin. Do not add
untrusted or wildcard origins.

### Frontend API troubleshooting

Run Django and Vite in separate PowerShell windows:

```powershell
# Repository root
.\backend\venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000

# Repository root, second window
cd frontend
npm run dev
```

Development is available at `http://127.0.0.1:5173/`. Production preview uses
`http://127.0.0.1:4173/` after `npm run build` and `npm run preview`. Both modes
proxy `/api/` and `/media/` to `VITE_DEV_PROXY_TARGET`.

Vite uses strict ports. If startup reports that port 5173 or 4173 is in use,
stop the older Vite terminal with `Ctrl+C` before restarting. Restart Vite and
refresh existing browser tabs after changing its configuration.

To diagnose routing, compare these direct and proxied URLs while both servers
are running:

```text
http://127.0.0.1:8000/api/categories/
http://127.0.0.1:5173/api/categories/
```

If the first returns JSON but the second returns a frontend 404 or 405, the
browser is not connected to the Vite instance using this repository's config.

Check and build the frontend:

```powershell
cd frontend
npm run lint
npm run build
npm run preview
```

The storefront formats the currency returned by the checkout API. Authentication
is held in Django's server-side session and survives page
reloads. The browser receives an HttpOnly `sessionid` cookie and a
JavaScript-readable `csrftoken`; unsafe API requests send the latter in the
`X-CSRFToken` header. Production settings require HTTPS for both cookies and
enable HTTPS redirect and HSTS.

## Stripe checkout and private invoices

Checkout totals and fulfillment are authoritative on Django. The browser requests
a quote, starts Stripe Checkout, and polls the internal checkout UUID after Stripe
redirects back. Only the signature-verified webhook creates an order, changes
stock, consumes a coupon, and clears the cart.

Successful fulfillment also sends one confirmation email to the checkout billing
address with the order number, purchased items, total, status, and order link.
Webhook retries do not send duplicate confirmations, and an SMTP failure does not
roll back a paid order.

Copy `backend/.env.example` to `backend/.env`, then add your Stripe test
credentials to the ignored backend environment file:

```text
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_GHS_TO_USD_RATE=0.065
STRIPE_SUCCESS_URL=http://127.0.0.1:5173/checkout/confirmation/{checkout_id}
STRIPE_CANCEL_URL=http://127.0.0.1:5173/checkout?cancelled=1
```

Never commit `.env` or paste its credentials into source code. Restart Django
after editing it. Confirm configuration without printing either secret:

```powershell
python backend/manage.py shell -c "from django.conf import settings; print('Stripe key configured:', bool(settings.STRIPE_SECRET_KEY)); print('Webhook secret configured:', bool(settings.STRIPE_WEBHOOK_SECRET))"
```

You can still set deployment values through the operating-system environment;
they override `.env` values.

Forward test events with the Stripe CLI:

```powershell
stripe listen --forward-to 127.0.0.1:8000/api/payments/stripe/webhook/
```

Use the `whsec_...` value printed by `stripe listen` as
`STRIPE_WEBHOOK_SECRET`, then restart Django.

The catalog is priced in GHS. If the connected Stripe account cannot present
GHS, Stripe Checkout charges the USD equivalent using
`STRIPE_GHS_TO_USD_RATE`. Keep this deployment setting current; each payment
transaction records the exact provider amount, currency, and conversion rate.

Optional commerce and invoice configuration:

```text
STORE_CURRENCY=USD
STORE_TAX_RATE=0.075
STORE_SHIPPING_FEE=10.00
STORE_FREE_SHIPPING_THRESHOLD=100.00
INVOICE_COMPANY_NAME=ECCO Store
INVOICE_COMPANY_ADDRESS=123 Commerce Avenue, Accra, Ghana
INVOICE_SUPPORT_EMAIL=support@example.com
INVOICE_TAX_ID=
```

Invoices are A5 portrait PDFs generated by WeasyPrint and stored below
`backend/private_media/invoices/`. This directory must not be mapped to a public web
route; downloads pass through the authenticated ownership-scoped API.

WeasyPrint also needs native Pango libraries. On Windows, install the current
MSYS2 runtime and its Pango dependencies as described in the
[official WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/latest/first_steps.html),
then ensure its DLL directory is available to Python. Linux deployments need the
distribution packages for Pango, Cairo, GDK-PixBuf, and libffi in addition to
`pip install -r backend/requirements.txt`.

With the default 64-bit MSYS2 installation, Django automatically uses:

```text
WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin
```

Override that environment variable before starting Django when the DLLs are
installed elsewhere. Verify the runtime with:

```powershell
python -m weasyprint --info
```

Create draft invoices for pre-Stripe orders (safe to rerun):

```powershell
python backend/manage.py backfill_invoices
```

The command does not mark legacy orders paid. If native PDF libraries are not
available, it retains the draft invoice record and reports that PDF generation
must be retried after installing them.

## Payment providers

Copy `backend/.env.example` to the ignored `backend/.env` and add only the providers that the
store should expose. New catalog prices and checkouts use Ghanaian cedi (`GHS`).
Existing finalized orders keep their stored currency.

- Stripe requires `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`.
- Paystack Ghana requires `PAYSTACK_SECRET_KEY`; configure the webhook as
  `/api/payments/paystack/webhook/`. Its hosted checkout provides cards, mobile
  money, and supported bank transfers.
- PayPal requires a REST app client ID/secret and webhook ID. Sandbox is the
  default API. Since PayPal Checkout does not charge GHS directly,
  `PAYPAL_GHS_TO_USD_RATE` converts and snapshots the USD provider amount.

Configure provider webhooks over HTTPS in their dashboards. Never place live
credentials in `.env.example` or frontend environment files. Restart Django
after changing `.env`. Staff can review internal transaction and revenue
summaries at `http://127.0.0.1:5173/staff/payments`; these reports are not bank
settlement statements.

Staff shipping management is available at
`http://127.0.0.1:5173/staff/shipping`. It lists orders ready to ship and manages
standard, express, and pickup methods, geographic zones, and rates. Courier and
tracking details are assigned from the staff order page. Configured rates are
reference data for now; checkout still uses `STORE_SHIPPING_FEE` and
`STORE_FREE_SHIPPING_THRESHOLD`.

Staff promotion management is available at
`http://127.0.0.1:5173/staff/discounts`. Staff can create coupons, scheduled
percentage promotions, and GHS gift cards. A newly issued gift-card code is
shown once; copy it immediately because only a keyed hash and masked suffix are
stored. Checkout applies the best eligible promotion per product, then one
coupon, then one gift card. Coupon usage and gift-card value are reserved while
a hosted payment is pending and finalized only after verified payment.

## Staff store settings

Superusers and staff assigned the `Can manage store settings` permission can
open `http://127.0.0.1:5173/staff/settings`. Store identity, contact details,
logo, tax rate, and customer email toggles are stored in the database. Tax
changes affect new checkout quotes only; completed orders keep their snapshots.

User and role administration remains superuser-only. Invited staff receive a
one-time password-setup link through the configured SMTP backend. Roles expose
only approved ecommerce permissions, and superuser access cannot be granted
through the REST API.

Payment and SMTP credentials remain in the ignored `.env`. The Settings page
reports only whether providers are configured and safe connection metadata; it
never returns secret keys or passwords. Restart Django after changing any
environment setting. 2FA, API keys, backup/restore, SMS/push notifications, and
external shipping, accounting, or marketing integrations are displayed as
unavailable until dedicated secure integrations are implemented.

## Production deployment: Vercel, Koyeb, Neon, and Cloudinary

Vercel hosts `frontend/`, Koyeb runs the Dockerized Django API, Neon provides
PostgreSQL, and Cloudinary stores persistent public images and authenticated
private invoices. Gmail SMTP sends transactional email. Local development keeps
using SQLite and local media when `DATABASE_URL` and `CLOUDINARY_URL` are absent.

### 1. Create Neon and Cloudinary resources

Create a Neon Free PostgreSQL project and copy its pooled connection URL. Create
a Cloudinary product environment and copy its server-side URL. Never commit
either value or expose `CLOUDINARY_URL` through a Vercel `VITE_*` variable.

Cloudinary delivery is split by asset type:

- Product primary/gallery images and the store logo use public image delivery.
- Invoice PDFs use authenticated raw delivery and five-minute signed URLs.
- Invoice downloads remain protected by the existing ownership-checked API.

### 2. Migrate existing SQLite data and media

Back up `backend/db.sqlite3`, `backend/media/`, and `backend/private_media/`,
stop local writes, and export to a directory outside Git:

```powershell
.\backend\venv\Scripts\python.exe backend\manage.py export_production_data C:\secure-transfer\ecco-production.json --confirm
```

The command writes a fixture plus a checksum manifest and excludes sessions,
admin logs, generated permissions, environment variables, and credentials.
Passwords remain hashed and primary keys, relationships, snapshots, provider
references, and historical currencies are preserved.

Temporarily set `DATABASE_URL` and `CLOUDINARY_URL` in the current PowerShell
process. Do not write production credentials to a tracked file:

```powershell
$env:DATABASE_URL="<Neon pooled PostgreSQL URL>"
$env:CLOUDINARY_URL="cloudinary://<api-key>:<api-secret>@<cloud-name>"
$env:DJANGO_DEBUG="false"
$env:DJANGO_SECRET_KEY="<temporary secure value>"

.\backend\venv\Scripts\python.exe backend\manage.py migrate --noinput
.\backend\venv\Scripts\python.exe backend\manage.py import_production_data C:\secure-transfer\ecco-production.json --confirm-empty
.\backend\venv\Scripts\python.exe backend\manage.py migrate_media_to_cloudinary `
  --source-media backend\media `
  --source-private-media backend\private_media `
  --confirm
```

Import refuses a populated application database, validates its manifest, runs
transactionally, and verifies model counts. Media migration validates paths and
images, uploads public and private assets using their correct storage classes,
and verifies the result. Clear the temporary environment variables afterward.

### 3. Deploy Django to Koyeb

Create a Web Service from
`https://github.com/SOA-WebCraft/react-django-eccommerce` using Docker, the
repository root, one Free instance, and either Frankfurt or Washington. The
container applies migrations on startup and launches Gunicorn on Koyeb's `PORT`.
Configure `/api/categories/` as the health-check path.

Set these Koyeb environment variables before deployment:

```text
DATABASE_URL=<Neon pooled PostgreSQL URL>
DJANGO_SECRET_KEY=<secure random value>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=<service>.koyeb.app
DJANGO_CSRF_TRUSTED_ORIGINS=https://<project>.vercel.app
CLOUDINARY_URL=cloudinary://<api-key>:<api-secret>@<cloud-name>
FRONTEND_BASE_URL=https://<project>.vercel.app
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=<sender@gmail.com>
EMAIL_HOST_PASSWORD=<Google app password>
DEFAULT_FROM_EMAIL=ECCO Store <sender@gmail.com>
STRIPE_SECRET_KEY=<secret-if-used>
STRIPE_WEBHOOK_SECRET=<webhook-secret-if-used>
PAYSTACK_SECRET_KEY=<secret-if-used>
PAYPAL_CLIENT_ID=<id-if-used>
PAYPAL_CLIENT_SECRET=<secret-if-used>
PAYPAL_WEBHOOK_ID=<id-if-used>
STRIPE_SUCCESS_URL=https://<project>.vercel.app/checkout/confirmation/{checkout_id}
STRIPE_CANCEL_URL=https://<project>.vercel.app/checkout?cancelled=1
PAYMENT_SUCCESS_URL=https://<project>.vercel.app/checkout/confirmation/{checkout_id}
PAYMENT_CANCEL_URL=https://<project>.vercel.app/checkout?cancelled=1
```

Use a Google app password, not the Gmail account password. The free Koyeb
filesystem is not persistent; all relational data must remain in Neon and all
uploaded files must remain in Cloudinary.

### 4. Deploy React to Vercel

Import the same GitHub repository with these settings:

```text
Root Directory: frontend
Install Command: npm ci
Build Command: npm run build
Output Directory: dist
VITE_API_BASE_URL=/api
BACKEND_API_ORIGIN=https://<service>.koyeb.app
```

`frontend/vercel.json` provides SPA routing. Server-side Vercel functions proxy
`/api/*` and `/media/*` to `BACKEND_API_ORIGIN`; that value is not included in
browser JavaScript. The browser therefore keeps same-origin secure session and
CSRF cookies. Redeploy Vercel after changing either environment variable.

After Vercel assigns its final domain, update every Koyeb frontend, CSRF, and
payment-return URL and redeploy the API.

### 5. Configure payment webhooks and verify

Configure only enabled payment providers:

```text
https://<service>.koyeb.app/api/payments/stripe/webhook/
https://<service>.koyeb.app/api/payments/paystack/webhook/
https://<service>.koyeb.app/api/payments/paypal/webhook/
```

Verify catalog browsing, authentication and CSRF, cart and checkout, Gmail
password-reset and purchase emails, public images, private invoice downloads,
provider redirects, signed webhooks, and idempotent fulfillment.

Production verification commands:

```powershell
.\backend\venv\Scripts\python.exe backend\manage.py check
.\backend\venv\Scripts\python.exe backend\manage.py check --deploy
.\backend\venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
Push-Location backend
.\venv\Scripts\python.exe manage.py test
Pop-Location
npm --prefix frontend run lint
npm --prefix frontend run build
docker build -t ecco-api .
```

Free Koyeb and Neon resources are appropriate for a hobby or demonstration
store. Monitor cold starts, Neon compute/storage allowances, Cloudinary usage,
and provider limits before accepting real production traffic.
