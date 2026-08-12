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

## Production deployment: Vercel and Render

Production uses Vercel for `frontend/`, a Docker web service and PostgreSQL on
Render, WhiteNoise for Django static files, and Cloudinary for persistent media.
Local development remains SQLite plus the local `backend/media/` and
`backend/private_media/`
directories when `DATABASE_URL` and `CLOUDINARY_URL` are absent.

### 1. Put the repository on GitHub

This workspace is not currently a Git repository. Review generated migration
fixtures before committing; `.env`, SQLite, local media, private invoices,
static output, and frontend build output are ignored.

```powershell
git init
git add .
git commit -m "Prepare ecommerce app for production"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

Do not add a real `.env`, exported production fixture, database backup, or media
archive to Git.

### 2. Create Cloudinary storage

Create a Cloudinary product environment and copy its server-side URL into
Render as `CLOUDINARY_URL`. The application uses authenticated server uploads:

- Product primary/gallery images and the store logo use public image delivery.
- Invoice PDFs use the `raw` resource type with `authenticated` delivery.
- Invoice downloads remain behind the existing ownership-checked Django API and
  use a five-minute signed Cloudinary download URL internally.

Never put `CLOUDINARY_URL` in Vercel or browser-visible `VITE_*` variables.

### 3. Create the Render Blueprint

Connect the GitHub repository from Render's **Blueprints** page and apply the
root [`render.yaml`](render.yaml). It provisions `ecco-api` and PostgreSQL.
The Docker image includes the native Pango libraries required by WeasyPrint;
the pre-deploy command applies migrations, and Gunicorn serves `config.wsgi`.

Set these Render variables before the first production payment:

```text
CLOUDINARY_URL=cloudinary://<api-key>:<api-secret>@<cloud-name>
FRONTEND_BASE_URL=https://<project>.vercel.app
DJANGO_CSRF_TRUSTED_ORIGINS=https://<project>.vercel.app
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=<sender>
EMAIL_HOST_PASSWORD=<app-password>
DEFAULT_FROM_EMAIL=ECCO Store <sender@example.com>
STRIPE_SECRET_KEY=<secret>
STRIPE_WEBHOOK_SECRET=<webhook-secret>
PAYSTACK_SECRET_KEY=<secret-if-used>
PAYPAL_CLIENT_ID=<id-if-used>
PAYPAL_CLIENT_SECRET=<secret-if-used>
PAYPAL_WEBHOOK_ID=<id-if-used>
STRIPE_SUCCESS_URL=https://<project>.vercel.app/checkout/confirmation/{checkout_id}
STRIPE_CANCEL_URL=https://<project>.vercel.app/checkout?cancelled=1
PAYMENT_SUCCESS_URL=https://<project>.vercel.app/checkout/confirmation/{checkout_id}
PAYMENT_CANCEL_URL=https://<project>.vercel.app/checkout?cancelled=1
```

`DATABASE_URL` and `DJANGO_SECRET_KEY` are supplied by the Blueprint. Render's
external hostname is automatically accepted by Django. Add custom hosts to
`DJANGO_ALLOWED_HOSTS` later if custom domains are introduced.

The health check is `GET /api/categories/`. Before accepting payments, configure
the provider dashboards with the production webhook endpoints:

```text
https://<api-service>.onrender.com/api/payments/stripe/webhook/
https://<api-service>.onrender.com/api/payments/paystack/webhook/
https://<api-service>.onrender.com/api/payments/paypal/webhook/
```

### 4. Deploy the frontend to Vercel

Import the same repository and use:

```text
Root Directory: frontend
Install Command: npm ci
Build Command: npm run build
Output Directory: dist
VITE_API_BASE_URL=/api
RENDER_API_ORIGIN=https://<api-service>.onrender.com
```

[`frontend/vercel.json`](frontend/vercel.json) provides SPA routing. Vercel
functions proxy `/api/*` and `/media/*` using the server-only
`RENDER_API_ORIGIN`; the value is not shipped in browser JavaScript. The browser
therefore keeps using same-origin `/api`, including Django's secure HttpOnly
session and CSRF cookies. Redeploy Vercel after changing environment variables.

### 5. Migrate existing SQLite data and media

First back up `backend/db.sqlite3`, `backend/media/`, and
`backend/private_media/`, stop local writes,
and export from the local SQLite environment to a directory outside Git:

```powershell
python backend/manage.py export_production_data C:\secure-transfer\ecco-production.json --confirm
```

The command exports approved application records only and creates
`ecco-production.manifest.json` with a SHA-256 checksum and model counts. It
excludes sessions, admin logs, content types, generated permissions, environment
variables, and credentials. Password hashes, primary keys, order snapshots,
payment references, and historical currencies are preserved.

Transfer both JSON files and the two media directories through a private channel.
On an empty, migrated Render database, upload the fixture to a temporary private
location and run:

```text
python manage.py import_production_data /secure/ecco-production.json --confirm-empty
python manage.py migrate_media_to_cloudinary \
  --source-media /secure/media \
  --source-private-media /secure/private_media \
  --confirm
```

Import refuses a populated application database, verifies the fixture checksum,
runs transactionally, and compares every model count. Media migration validates
all source paths and images before upload, then verifies every Cloudinary asset.
Do not enable writes or payment webhooks until both commands succeed. Verify the
superuser login, representative product images, a private invoice download,
catalog/order counts, email, checkout, and webhook delivery afterward. Delete
the temporary fixture and media archive when the migration has been audited.

For a fresh production environment, skip export/import and create an admin from
the Render Shell only after migrations:

```text
python manage.py createsuperuser
```

### Production verification commands

```text
python backend/manage.py check
python backend/manage.py check --deploy
python backend/manage.py makemigrations --check --dry-run
cd backend && python manage.py test
python backend/manage.py collectstatic --noinput
```

Run `docker build -t ecco-api .` on a machine with Docker before applying the
Blueprint, then smoke-test PDF generation and Gunicorn locally. No external
service, database, domain, or provider account is created by repository setup.
