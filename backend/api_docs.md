# Ecommerce API

All URLs use JSON and have trailing slashes. Authentication uses Django's
server-side session. Browsers must include credentials on requests:

```js
fetch("/api/cart/", { credentials: "include" })
```

The authentication credential is an HttpOnly `sessionid` cookie. Before login,
registration, or any other unsafe request, call `GET /api/users/csrf/`, read the
JavaScript-accessible `csrftoken` cookie, and send it as `X-CSRFToken`. Cookies
use `SameSite=Lax` locally. Production defaults to `SameSite=None` and Secure so
Apple's cross-site form-post callback can retain OAuth state; HTTPS is required.

List responses are paginated with `count`, `next`, `previous`, and `results`.
Validation errors use DRF's field-based JSON structure. Unless noted otherwise,
authenticated failures return `401`, permission failures return `403`, and missing
or inaccessible objects return `404`.

## Users and authentication

### GET `/api/users/social-providers/`

Returns the supported social sign-in providers and whether each is configured.
Authentication, parameters, and a request body are not required. Provider
credentials are never included.

Success — `200 OK`:

```json
{"results":[{"provider":"google","label":"Google","enabled":true},{"provider":"linkedin","label":"LinkedIn","enabled":false}]}
```

### GET `/api/users/social-login/{provider}/`

Starts sign-up or sign-in with `google`, `apple`, `facebook`, or `linkedin` and
redirects to that provider. An optional relative `next` query parameter controls
the post-login frontend destination; external destinations are rejected. No
authentication or request body is required. An unknown provider returns `404`;
an unconfigured provider returns `503`.

### GET/POST `/api/users/social-login/{provider}/callback/`

OAuth callback used by the configured provider. It validates provider state and
the signed identity response, requires a verified email, creates or links the
local account, creates a normal secure Django session, and redirects to
`/auth/social/callback` on the configured frontend. Apple uses `POST`; the other
providers normally use `GET`. Provider access tokens are not stored. Failed,
denied, or ambiguous-email callbacks redirect with a safe error message.


### GET `/api/users/csrf/`

Initializes the CSRF cookie. Authentication, parameters, and a request body are
not required.

Success — `200 OK`:

```json
{"detail": "CSRF cookie set."}
```

The response sets `csrftoken`. Send its value in `X-CSRFToken` on subsequent
`POST`, `PUT`, `PATCH`, and `DELETE` requests.

### POST `/api/users/register/`

Creates a customer account. Authentication is not required. Username and email
are required and must be unique; email uniqueness is case-insensitive. The
username must contain at least three characters. The password must pass Django's
configured password validators and match the required `confirm_password`
field. All registration validation is performed by the API. A valid CSRF cookie
and `X-CSRFToken` header are required.

Request:

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "A-long-safe-password-482!",
  "confirm_password": "A-long-safe-password-482!"
}
```

Success — `201 Created`:

```json
{"id": 1, "username": "alice", "email": "alice@example.com"}
```

Errors — `400 Bad Request`:

```json
{"username": ["A user with that username already exists."]}
```

```json
{"email": ["An account with this email address already exists."]}
```

```json
{"password": ["This password is too short."]}
```

```json
{"confirm_password": ["Passwords do not match."]}
```

`password` and `confirm_password` are write-only and are never returned.

### POST `/api/users/email-availability/`

Validates an email while the registration form is being completed. The public
endpoint requires a CSRF cookie/header and is throttled to 60 requests per hour
per client. It accepts no authentication and returns no account details. Email
format and case-insensitive availability are validated by Django; final
registration repeats the same availability check and remains authoritative.

Request:

```json
{"email": "alice@example.com"}
```

Success — `200 OK`:

```json
{"available": true}
```

Existing or invalid email — `400 Bad Request`:

```json
{"email": ["An account with this email address already exists."]}
```

Missing or invalid CSRF returns `403 Forbidden`; exceeding the rate limit
returns `429 Too Many Requests`.

### GET `/api/users/me/`

Returns the authenticated user's safe profile fields. No parameters or request
body. Requires a valid session.

Success — `200 OK`:

```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "first_name": "Alice",
  "last_name": "Example",
  "phone": "+233 20 000 0000",
  "address": "1 Main Street",
  "city": "Accra",
  "postal_code": "10000",
  "country": "Ghana",
  "can_manage_orders": false,
  "can_manage_catalog": false,
  "can_manage_settings": false
}
```

`can_manage_orders` identifies active staff who may access order management and
analytics. `can_manage_catalog` identifies active staff assigned the existing
`Catalog Managers` permissions and controls access to the frontend product
management dashboard. `can_manage_settings` identifies superusers and staff
assigned the store-settings permission. All capability fields are read-only and cannot be supplied by a
client.

Error — `401 Unauthorized`:

```json
{"detail": "Authentication credentials were not provided."}
```

### PATCH `/api/users/me/`

Updates the authenticated user's own account and profile. A valid session and
CSRF token are required. Editable fields are `email`, `first_name`, `last_name`,
`phone`, `address`, `city`, `postal_code`, and `country`. Omitted fields remain
unchanged. Sending `null` or an empty string clears an optional profile field to
database `NULL`. Username, IDs, permissions, timestamps, and passwords cannot be
updated here. `PUT` is unsupported and returns `405 Method Not Allowed`.

Changing `email` requires `current_password`; profile-only changes do not. The
new email must not already belong to another account, using case-insensitive
matching.
`current_password` is write-only and is never returned.

Request:

```json
{
  "email": "alice.new@example.com",
  "first_name": "Alice",
  "phone": null,
  "address": "1 Main Street",
  "city": "Accra",
  "postal_code": "10000",
  "country": "Ghana",
  "current_password": "A-long-safe-password-482!"
}
```

Success — `200 OK` returns the complete safe profile representation shown above.

Errors — `400 Bad Request`:

```json
{"current_password": "Enter your current password to change email."}
```

```json
{"username": "This field cannot be updated."}
```

Invalid email and maximum-length errors use the corresponding field name.
Unauthenticated requests return `401`; missing or invalid CSRF returns `403`.

### POST `/api/users/login/`

Authenticates an email address and password, rotates the session identifier, and
returns the safe user profile. Authentication is not required, but a valid CSRF
cookie and `X-CSRFToken` header are required.

Email matching is case-insensitive. New registrations and profile email changes
must use an email address that is not already assigned to another account.

Request:

```json
{"email": "alice@example.com", "password": "A-long-safe-password-482!"}
```

Success — `200 OK`:

```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "first_name": null,
  "last_name": null,
  "phone": null,
  "address": null,
  "city": null,
  "postal_code": null,
  "country": null,
  "can_manage_orders": false
}
```

`can_manage_orders` is read-only and is `true` for active staff users.

Error — `401 Unauthorized`:

```json
{"detail": "Invalid email or password."}
```

Malformed or missing fields return `400 Bad Request` using DRF field errors:

```json
{
  "email": ["Enter a valid email address."],
  "password": ["This field is required."]
}
```

The response sets a new HttpOnly `sessionid` cookie. Missing or invalid CSRF
tokens return `403 Forbidden`.

### POST `/api/users/logout/`

Destroys the current server-side session. Requires session authentication and a
valid CSRF token. It accepts no request body.

Success returns `204 No Content`. An unauthenticated request returns
`401 Unauthorized`; a missing or invalid CSRF token returns `403 Forbidden`.

### POST `/api/users/password-reset/`

Requests a one-time password-reset link by email. Authentication is not required,
but a valid CSRF cookie and `X-CSRFToken` header are required. The response is
identical for known, unknown, inactive, and unusable-password accounts so it does
not reveal whether an account exists. Limited to five requests per hour per
client; excess requests return `429 Too Many Requests`.

Request:

```json
{"email": "alice@example.com"}
```

Success — `200 OK`:

```json
{"detail": "If an active account exists for that email address, a password reset link has been sent."}
```

Invalid email input returns `400 Bad Request`; missing or invalid CSRF returns
`403 Forbidden`.

### POST `/api/users/password-reset/confirm/`

Sets a new password using the `uid` and single-use `token` from the emailed
frontend link. Authentication is not required, but CSRF is required. Links expire
after one hour. The password must pass Django's configured validators and match
`confirm_password`. Limited to ten attempts per hour per client.

Request:

```json
{
  "uid": "MQ",
  "token": "d0-example-token",
  "new_password": "Another-safe-password-593!",
  "confirm_password": "Another-safe-password-593!"
}
```

Success — `200 OK`:

```json
{"detail": "Your password has been reset successfully."}
```

Errors — `400 Bad Request`:

```json
{"token": "This password reset link is invalid or has expired."}
```

```json
{"confirm_password": ["Passwords do not match."]}
```

Password validation errors are returned under `new_password`. Missing CSRF
returns `403 Forbidden`; throttled attempts return `429 Too Many Requests`.

The former `/api/token/` and `/api/token/refresh/` JWT endpoints have been
removed and return `404 Not Found`.

## Staff customers

These read-only endpoints require an authenticated active staff account.
Staff accounts are excluded from customer results. `total_spent` includes paid
orders only, while `orders` counts every finalized customer order.

### GET `/api/staff/customers/`

Returns a paginated customer list. Optional `search` matches username, name,
email, or phone. Optional `status` accepts `active` or `inactive`; `page`
selects the results page. There is no request body.

Success — `200 OK`:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{
    "id": 12,
    "username": "alice",
    "name": "Alice Example",
    "email": "alice@example.com",
    "phone": "+233200000000",
    "orders": 3,
    "total_spent": "425.50",
    "status": "active",
    "date_joined": "2026-08-11T09:00:00Z"
  }]
}
```

Invalid status returns `400`; unauthenticated requests return `401`, and
authenticated non-staff requests return `403`.

### GET `/api/staff/customers/{id}/`

Returns the safe customer summary plus personal details, the latest 20 orders,
and the address stored in the customer's profile. `id` is the integer user ID.
Passwords, permission fields, and staff accounts are never returned. There is
no request body.

Success — `200 OK` includes:

```json
{
  "id": 12,
  "username": "alice",
  "name": "Alice Example",
  "email": "alice@example.com",
  "phone": "+233200000000",
  "orders": 3,
  "total_spent": "425.50",
  "status": "active",
  "date_joined": "2026-08-11T09:00:00Z",
  "personal_details": {
    "first_name": "Alice",
    "last_name": "Example",
    "phone": "+233200000000",
    "email": "alice@example.com"
  },
  "order_history": [],
  "saved_addresses": [{
    "address": "1 Main Street",
    "city": "Accra",
    "postal_code": "10000",
    "country": "Ghana"
  }]
}
```

Missing customers return `404`; authentication and permission failures return
`401` and `403` respectively. Wishlist and review data are not returned because
those resources do not exist in the current API.

## Staff inventory

All inventory endpoints require an authenticated active staff account. Reserved
stock is the quantity in Stripe checkout attempts whose status is `created` or
`paid`; customer carts do not reserve stock. All writes require CSRF protection.

### GET `/api/staff/inventory/stock/`

Returns paginated product stock levels. Optional `search` matches product names;
`state` accepts `in_stock`, `low_stock`, or `out_of_stock`; `page` selects a
page. Available stock is `max(current - reserved, 0)`. Low stock is positive
available stock at or below `minimum_stock_quantity`.

Success — `200 OK`:

```json
{"count":1,"next":null,"previous":null,"results":[{"id":1,"name":"Store Phone","slug":"store-phone","category_name":"Smartphones","stock_quantity":10,"minimum_stock_quantity":5,"reserved_stock":2,"available_stock":8,"stock_state":"in_stock","is_active":true}]}
```

Invalid state returns `400`; unauthenticated and non-staff requests return `401`
and `403`.

### POST `/api/staff/inventory/adjustments/`

Atomically adds, removes, or sets product stock and creates an immutable movement.
`add` and `remove` require a positive quantity; `set` permits zero. Removing more
than current stock returns `400` without changing inventory.

```json
{"product":1,"operation":"remove","quantity":2,"note":"Damaged units"}
```

Success — `201 Created` returns the movement with product, signed change,
previous/resulting stock, staff username, note, and timestamp. Invalid fields or
insufficient stock return `400`; missing products return `400`.

### GET `/api/staff/inventory/movements/`

Returns paginated immutable stock history. Optional `product` filters by integer
product ID and `page` selects a page. Each result includes `movement_type`,
`quantity_change`, previous/resulting stock, note, purchase-order reference,
staff username, and creation time. Success is `200`; authentication failures are
`401` or `403`.

### GET/POST `/api/staff/inventory/suppliers/`

`GET` returns paginated suppliers. `POST` creates one from `name`, optional
`phone`, optional `email`, and optional `products` (product ID array).

```json
{"name":"Phone Supplier","phone":"+233200000000","email":"sales@example.com","products":[1,2]}
```

Creation returns `201`; validation failures return `400`.

### GET/PATCH/DELETE `/api/staff/inventory/suppliers/{id}/`

Retrieves, partially updates, or deletes a supplier. PATCH accepts the same
writable fields as creation and returns `200`; DELETE returns `204`. A supplier
referenced by a purchase order cannot be deleted and returns a protected-resource
error. Missing suppliers return `404`.

### GET/POST `/api/staff/inventory/purchase-orders/`

`GET` returns paginated purchase orders and optionally filters by `status`
(`ordered`, `received`, or `cancelled`). `POST` atomically creates an ordered
purchase order with at least one unique product.

```json
{"supplier":1,"notes":"Monthly restock","items":[{"product":1,"quantity":5,"unit_cost":"80.00"}]}
```

Creation returns `201` with supplier, items, total cost, creator, and timestamps.
Invalid/duplicate/empty items return `400`.

### GET `/api/staff/inventory/purchase-orders/{id}/`

Returns one purchase order with its supplier and items. Success is `200`; missing
orders return `404`.

### POST `/api/staff/inventory/purchase-orders/{id}/receive/`

Atomically receives an ordered purchase order, adds every item quantity to stock,
records one movement per item, and marks the order received. The request body is
empty. Success returns the updated order with `200`. Receiving a received or
cancelled order returns `400` and never changes stock twice.

### POST `/api/staff/inventory/purchase-orders/{id}/cancel/`

Cancels an ordered purchase order without changing stock. The request body is
empty. Success returns the updated order with `200`; received or already-cancelled
orders return `400`.

## Categories

Category reads are public. Creates, updates, and deletes require the matching
Django category model permission. The automatically provisioned
`Catalog Managers` group has these permissions; superusers have them implicitly.

### GET `/api/categories/`

Returns a paginated category list. It has no supported query parameters.

Success — `200 OK`:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{"id": 1, "name": "Books", "slug": "books"}]
}
```

### POST `/api/categories/`

Creates a category. Both `name` and `slug` must be unique.

Request:

```json
{"name": "Books", "slug": "books"}
```

Success — `201 Created`:

```json
{"id": 1, "name": "Books", "slug": "books"}
```

Error — `400 Bad Request`:

```json
{"slug": ["category with this slug already exists."]}
```

### GET `/api/categories/{id}/`

Returns one category. `id` is the integer category ID. No request body.

Success — `200 OK`:

```json
{"id": 1, "name": "Books", "slug": "books"}
```

### PUT `/api/categories/{id}/`

Fully replaces a category and requires the category change permission. `id` is the integer
category ID. All writable fields are required.

Request:

```json
{"name": "Technical Books", "slug": "technical-books"}
```

Success — `200 OK` returns the updated category. Missing or invalid fields return
`400 Bad Request`; users without the required permission receive `403 Forbidden`.

### PATCH `/api/categories/{id}/`

Partially updates a category and requires the category change permission.

Request:

```json
{"name": "Technical Books"}
```

Success — `200 OK` returns the updated category. Validation errors return `400`.

### DELETE `/api/categories/{id}/`

Deletes a category and requires the category delete permission. It accepts no request body.
Success returns `204 No Content`. A category referenced by products cannot be
deleted; the API returns an error rather than deleting its products.

## Products

Product reads are public, but clients without catalog permissions can only see
active products. Users with the product change permission can read inactive
products. Writes require the matching add, change, or delete model permission.

Product list query parameters:

- `category`: exact category slug.
- `min_price`, `max_price`: nonnegative decimal bounds.
- `search`: product-name search.
- `ordering`: `name`, `price`, or `created_at`; prefix with `-` to reverse.
- `is_active`: `true` or `false`, available to catalog managers only.
- `page`: positive page number.

### GET `/api/products/`

Returns a filtered, paginated product list.

Success — `200 OK`:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{
    "id": 1,
    "name": "Django Book",
    "slug": "django-book",
    "description": "",
    "image": null,
    "gallery_images": [],
    "price": "25.00",
    "stock_quantity": 5,
    "is_active": true,
    "category": 1,
    "category_name": "Books",
    "created_at": "2026-07-28T20:00:00Z",
    "updated_at": "2026-07-28T20:00:00Z"
  }]
}
```

Error — `400 Bad Request`:

```json
{"min_price": "Must be a valid decimal number."}
```

### POST `/api/products/`

Creates a product. Requires the product add permission. Price and stock must be
nonnegative, and `category` must identify an existing category. The optional
`image` must be a JPEG, PNG, or WebP file no larger than 5 MB. Use
`multipart/form-data` when uploading an image; JSON remains supported otherwise.

Request:

```json
{
  "name": "Django Book",
  "slug": "django-book",
  "description": "",
  "image": "<binary JPEG, PNG, or WebP file>",
  "price": "25.00",
  "stock_quantity": 5,
  "is_active": true,
  "category": 1
}
```

Success — `201 Created` returns the full product representation.

Error — `400 Bad Request`:

```json
{"price": ["Ensure this value is greater than or equal to 0."]}
```

```json
{"image": ["Only JPEG, PNG, and WebP images are supported."]}
```

```json
{"image": ["Image size must not exceed 5 MB."]}
```

### GET `/api/products/{slug}/`

Returns one visible product. `slug` is the product's unique slug. An inactive product
returns `404` to clients without catalog permissions. Success returns `200 OK` and the product shape
shown above.

### PUT `/api/products/{slug}/`

Fully replaces a product and requires the product change permission. `slug` is the
product's unique slug. All required writable fields must be supplied.

Request:

```json
{
  "name": "Updated Django Book",
  "slug": "updated-django-book",
  "description": "",
  "image": "<binary JPEG, PNG, or WebP file>",
  "price": "22.50",
  "stock_quantity": 8,
  "is_active": true,
  "category": 1
}
```

Success — `200 OK` returns the updated product. Use multipart data to replace the
image, omit the optional image to retain it, or submit `null` in JSON to clear it.
Missing, invalid, or negative values return `400 Bad Request`; users without permission
receive `403 Forbidden`.

### PATCH `/api/products/{slug}/`

Partially updates a product and requires the product change permission.

Request:

```json
{"price": "22.50", "stock_quantity": 8, "image": null}
```

Success — `200 OK` returns the updated product. Image replacement uses multipart
data; JSON `null` clears the image. Invalid data returns `400`.

### DELETE `/api/products/{slug}/`

Deletes a product and requires the product delete permission. It accepts no request body.
Success returns `204 No Content`.

### GET `/api/products/{id}/images/`

Returns the product's additional gallery images in upload order. Authentication
is not required for active products. Public clients receive `404 Not Found` for
inactive products; catalog managers may view them. `id` is the integer product ID.

Success — `200 OK`:

```json
[
  {
    "id": 11,
    "image": "http://testserver/media/product_images/gallery/front.png",
    "created_at": "2026-07-28T22:00:00Z"
  },
  {
    "id": 12,
    "image": "http://testserver/media/product_images/gallery/back.webp",
    "created_at": "2026-07-28T22:01:00Z"
  }
]
```

Relevant status codes: `200`, `404`.

### POST `/api/products/{id}/images/`

Uploads one or several additional product images. Requires the product-image add
permission. Send `multipart/form-data` with one or more repeated `images` fields. Every
file must be a valid JPEG, PNG, or WebP image no larger than 5 MB. The primary
product `image` does not count toward the maximum of 10 gallery images.

Request:

```text
images=<front.png>
images=<back.webp>
```

Success — `201 Created`:

```json
[
  {
    "id": 11,
    "image": "http://testserver/media/product_images/gallery/front.png",
    "created_at": "2026-07-28T22:00:00Z"
  },
  {
    "id": 12,
    "image": "http://testserver/media/product_images/gallery/back.webp",
    "created_at": "2026-07-28T22:01:00Z"
  }
]
```

Errors — `400 Bad Request`:

```json
{"images": ["This field is required."]}
```

```json
{"images": "A product may have at most 10 gallery images."}
```

```json
{"images": {"1": ["Only JPEG, PNG, and WebP images are supported."]}}
```

Unauthenticated requests return `401 Unauthorized`; authenticated users without permission
requests return `403 Forbidden`. A missing product returns `404 Not Found`.
Relevant status codes: `201`, `400`, `401`, `403`, `404`.

### DELETE `/api/products/{id}/images/{image_id}/`

Deletes one gallery image belonging to the specified product and removes its file
after the transaction commits. Requires the product-image delete permission. Both path
parameters are integer IDs. An image belonging to another product is treated as
not found. No request body is accepted.

Success — `204 No Content`.

Errors:

```json
{"detail": "Not found."}
```

Relevant status codes: `204`, `401`, `403`, `404`.

## Cart

Every cart endpoint explicitly requires session authentication and operates only on
the current user's cart. User IDs are never accepted. Missing or invalid
authentication returns `401 Unauthorized` before cart data is accessed.

### GET `/api/cart/`

Returns the current cart, creating an empty cart if necessary.

Success — `200 OK`:

```json
{
  "id": 1,
  "items": [{
    "id": 1,
    "product": 1,
    "product_detail": {
      "id": 1,
      "name": "Django Book",
      "slug": "django-book",
      "description": "",
      "image": "http://testserver/media/product_images/django-book.png",
      "gallery_images": [],
      "price": "25.00",
      "stock_quantity": 5,
      "is_active": true,
      "category": 1,
      "category_name": "Books",
      "created_at": "2026-07-28T20:00:00Z",
      "updated_at": "2026-07-28T20:00:00Z"
    },
    "quantity": 2,
    "line_total": "50.00"
  }],
  "total": "50.00",
  "created_at": "2026-07-28T20:00:00Z",
  "updated_at": "2026-07-28T20:00:00Z"
}
```

### POST `/api/cart/items/`

Adds one active product. Quantity must be positive and cannot exceed current
stock. If the product is already present, the submitted quantity is added to its
existing quantity; the combined quantity cannot exceed stock. The database keeps
one row per product in each cart.

Request:

```json
{"product": 1, "quantity": 2}
```

New-item success — `201 Created`:

```json
{
  "id": 1,
  "product": 1,
  "product_detail": {
    "id": 1,
    "name": "Django Book",
    "slug": "django-book",
    "description": "",
    "image": "http://testserver/media/product_images/django-book.png",
    "gallery_images": [],
    "price": "25.00",
    "stock_quantity": 5,
    "is_active": true,
    "category": 1,
    "category_name": "Books",
    "created_at": "2026-07-28T20:00:00Z",
    "updated_at": "2026-07-28T20:00:00Z"
  },
  "quantity": 2,
  "line_total": "50.00"
}
```

Existing-item success — `200 OK` returns the same response shape with the
combined quantity and recalculated line total.

Errors — `400 Bad Request`:

```json
{"quantity": ["Quantity exceeds available stock."]}
```

```json
{"quantity": ["Combined quantity exceeds available stock."]}
```

### PATCH `/api/cart/items/{id}/`

Increments or decrements the quantity of an owned cart item. `id` is the integer
cart-item ID. Django performs the arithmetic, validates stock, and recalculates
the returned line total.

Request:

```json
{"operation": "increment"}
```

`operation` must be either `increment` or `decrement`. Decrementing below one
returns `400`; remove the item with `DELETE` instead. Incrementing beyond stock
also returns `400`. Success — `200 OK` returns the updated cart item with its
server-calculated `quantity` and `line_total`; an item belonging to another user
returns `404`.

### DELETE `/api/cart/items/{id}/`

Deletes an owned cart item. It accepts no request body. Success returns
`204 No Content`; another user's or missing item returns `404`.

## Orders

Every order endpoint requires session authentication. Customers can access only
their own orders. Active users with `is_staff=true` can list and retrieve every
finalized order, but this grants no API write access. Prices, totals, payment
fields, ownership, and order items are read-only. Orders are created only by a
verified Stripe webhook. Checkout attempts and invoices remain owner-scoped,
including for staff users.

### GET `/api/staff/analytics/`

Returns staff ecommerce metrics. Revenue, daily sales, and top products include
only finalized orders whose `payment_status` is `paid`. Status and total-order
counts include every finalized order. The daily series covers the latest 30
calendar days, including days with no sales. The `statistics` object compares
that period with the preceding 30 days. A growth percentage is `null` when the
previous period is zero and the current period has activity. Low stock means an
active product with five or fewer units.

- Authentication: required (session authentication).
- Permission: active Django staff users only.
- Path/query parameters: none.
- Request body: none.

Success — `200 OK`:

```json
{
  "summary": {
    "total_revenue": "1249.50",
    "paid_orders": 8,
    "total_orders": 10,
    "customers": 6
  },
  "statistics": {
    "period_days": 30,
    "revenue": "1249.50",
    "revenue_change_percent": "18.4",
    "paid_orders": 8,
    "paid_orders_change_percent": "14.3",
    "average_order_value": "156.19",
    "units_sold": 14,
    "unique_customers": 6,
    "repeat_customer_rate": "33.3",
    "new_customers": 2
  },
  "orders_by_status": [
    {"status": "pending", "count": 2},
    {"status": "processing", "count": 5},
    {"status": "shipped", "count": 1},
    {"status": "delivered", "count": 2},
    {"status": "cancelled", "count": 0}
  ],
  "daily_sales": [
    {"date": "2026-07-13", "revenue": "0.00", "orders": 0},
    {"date": "2026-08-11", "revenue": "249.50", "orders": 2}
  ],
  "top_products": [
    {"product_id": 7, "product_name": "Google Pixel 9 Pro", "quantity_sold": 5, "revenue": "499.50"}
  ],
  "low_stock_products": [
    {"id": 7, "name": "Google Pixel 9 Pro", "slug": "google-pixel-9-pro", "stock_quantity": 3, "category": "Smartphones"}
  ]
}
```

Errors:

- `401 Unauthorized`: no authenticated session.
- `403 Forbidden`: the authenticated user is not staff.
- `500 Internal Server Error`: a generic server error without internal details.

### POST `/api/staff/analytics/socket-ticket/`

Creates a short-lived ticket for the staff analytics WebSocket. The ticket is
bound to the authenticated staff user, expires after 60 seconds, grants only
read access to analytics snapshots, and must not be stored.

- Authentication: required (session authentication and CSRF protection).
- Permission: active Django staff users only.
- Path/query parameters: none.
- Request body: `{}`.

Success — `200 OK`:

```json
{
  "ticket": "signed-short-lived-value",
  "websocket_url": "wss://api.example.com/ws/staff/analytics/",
  "expires_in": 60
}
```

Errors:

- `401 Unauthorized`: no authenticated session.
- `403 Forbidden`: the authenticated user is not staff or CSRF validation failed.

### WebSocket `/ws/staff/analytics/?ticket={ticket}`

Streams a fresh analytics snapshot at the configured interval. Obtain the
ticket immediately beforehand from the socket-ticket endpoint. The connection
is rejected with close code `4403` for a missing, invalid, expired, inactive,
or non-staff identity.

```json
{
  "type": "analytics.snapshot",
  "data": {
    "summary": {},
    "statistics": {},
    "orders_by_status": [],
    "daily_sales": [],
    "top_products": [],
    "low_stock_products": []
  },
  "sent_at": "2026-08-14T12:00:00+00:00"
}
```

### GET `/api/orders/`

Returns the current customer's paginated order history, or all finalized orders
for staff. Optional `status` accepts `pending`, `processing`, `shipped`,
`delivered`, or `cancelled`;
`page` selects a page.

Success — `200 OK`:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{
    "id": 1,
    "order_number": "A7K9M2P4QX",
    "status": "processing",
    "total": "50.00",
    "items": [{
      "id": 1,
      "product": 1,
      "product_name": "Django Book",
      "unit_price": "25.00",
      "quantity": 2,
      "line_total": "50.00"
    }],
    "created_at": "2026-07-28T20:00:00Z",
    "updated_at": "2026-07-28T20:00:00Z"
  }]
}
```

Each order in a staff response additionally includes its customer. This object is
never included in an ordinary customer's response:

```json
"customer": {
  "id": 7,
  "username": "alice",
  "email": "alice@example.com"
}
```

Error — `400 Bad Request`:

```json
{"status": "Must be a valid order status."}
```

Orders created after a verified Stripe payment begin with order status
`processing` and payment status `paid`. Payment and fulfillment states are
independent.

### POST `/api/orders/` (removed)

This former endpoint now returns `405 Method Not Allowed`. Order creation is
webhook-only. The retired behavior was: creates an order from the current cart. The body must be empty; client-supplied
prices, totals, users, statuses, and items are ignored because all fields are
server-controlled. Creation rechecks active state and stock atomically, snapshots
the product name and price, decrements stock, and clears the cart only on success.

Request:

```json
{}
```

Success — `201 Created` returns the order representation shown above.

Errors — `400 Bad Request`:

```json
{"cart": "An order cannot be created from an empty cart."}
```

```json
{"items": {"1": "Quantity exceeds available stock."}}
```

### GET `/api/orders/{id}/`

Returns one order belonging to the current customer; staff may retrieve any
finalized order. `id` is the integer order ID. It accepts no request body. Success
returns `200 OK` and the representation shown above, including `customer` only
for staff. A missing order, or another customer's order requested by a non-staff
user, returns `404`.

`order_number` is the immutable public order identifier. It contains exactly 10
uppercase letters and digits and is unique. The integer `id` remains the path
parameter for backward compatibility.

### PATCH `/api/orders/{id}/`

Advances an order to its next fulfillment status. This method requires an
authenticated active staff user and a valid CSRF token. Customers receive `403
Forbidden`. Only `status` and, when shipping, `tracking_number` are accepted;
ownership, customer data, items, totals, payment fields, and addresses cannot
be changed.

Allowed forward transitions are `pending` to `processing`, `processing` to
`shipped`, and `shipped` to `delivered`. Pending or processing orders may be
cancelled. Shipping requires a tracking number. Repeating the current status is
an idempotent success. Skipped, reversed, and post-shipping cancellations are
rejected. Successful changes add a timeline event.

Request:

```json
{"status": "shipped", "tracking_number": "TRACK-203948"}
```

Success — `200 OK` returns the staff order representation shown above, including
the read-only `customer` object.

Errors — `400 Bad Request`:

```json
{"status": "Order status must advance to the next status."}
```

```json
{"total": "This field cannot be updated."}
```

Errors may also be `401 Unauthorized`, `403 Forbidden`, or `404 Not Found`.
`PUT /api/orders/{id}/` remains unsupported and returns `405 Method Not Allowed`.

Order responses also include shipping fields, `courier`, `tracking_number`, `shipped_at`,
`delivered_at`, `cancelled_at`, a read-only `timeline` array, and the current
`return_request` and `refund_request` objects when present. The read-only
`payment_provider` field identifies the provider that completed the payment,
such as `stripe` or `paystack`; `payment_method` separately describes the
provider channel, such as `Card` or `Mobile Money`. Historical orders without a
linked payment transaction return `null` when their provider cannot be safely
determined.

### POST `/api/orders/{id}/returns/`

Creates a return request for the authenticated customer's own delivered, paid
order. Customers create requests from their order-detail page. One request is
allowed per order. The request body is `{"reason": "The item arrived damaged
and I would like to return it."}`. Success returns the request with `201
Created`. Ineligible or duplicate requests return `400`; unauthenticated access
returns `401`; missing or unowned orders return `404`.

### GET `/api/staff/returns/`

Returns paginated return requests for active staff. Optional `status` accepts
`requested`, `approved`, `rejected`, or `received`. Results include the order
number, customer, reason, staff note, status, and timestamps. Errors are `401`
or `403` when authentication or staff permission is missing.

### GET, PATCH `/api/staff/returns/{id}/`

Retrieves or updates one return request for active staff. PATCH accepts `status`
and optional `staff_note`. Allowed transitions are `requested` to `approved` or
`rejected`, then `approved` to `received`. Invalid transitions return `400`;
missing records return `404`. Example:

```json
{"status": "approved", "staff_note": "Return label sent."}
```

### GET `/api/staff/refunds/`

Returns active staff a paginated full-refund history containing order, customer,
amount, Stripe refund ID, status, error, requester, and timestamps. Errors are
`401` or `403` when required.

### POST `/api/staff/orders/{id}/refund/`

Issues a full refund through the order's original Stripe, Paystack, or PayPal
provider. Active staff send an empty body; the amount always comes from the
server-stored total. Success returns the refund record; immediately completed
refunds mark payment `refunded`, while an asynchronous provider response remains
`processing`. Unpaid, already-refunded, or provider-rejected orders return
`400`; other errors are `401`, `403`, or `404`.

### POST `/api/staff/orders/{id}/send-email/`

Sends the current status and tracking information to the billing email. Active
staff send an empty body. Success returns `200 OK` with
`{"detail": "Order status email sent."}` and adds a timeline event. A missing
email or mail failure returns `400`; other errors are `401`, `403`, or `404`.

## Discounts, promotions, and gift cards

All `/api/staff/discounts/` endpoints require an authenticated active staff
user. Unauthenticated requests return `401`; non-staff users receive `403`.

### GET, POST `/api/staff/discounts/coupons/`

Lists or creates coupons with `code`, `discount_type` (`fixed` or
`percentage`), positive `value`, nonnegative `minimum_subtotal`, optional
`starts_at`, `ends_at`, and `usage_limit`, plus `is_active`. Codes are normalized
to uppercase. Percentage values cannot exceed 100 and expiry must follow start.
Usage and reservation counts are read-only. Creation returns `201`; invalid or
duplicate data returns field-level `400`.

### GET, PATCH, DELETE `/api/staff/discounts/coupons/{id}/`

Retrieves, partially updates, or deletes one coupon. Success returns `200` or
`204`; missing records return `404`; PUT returns `405`.

### GET, POST `/api/staff/discounts/promotions/`

Lists or creates scheduled percentage promotions. Fields are `name`, percentage
from 0.01 through 100, scope (`store`, `categories`, or `products`), category and
product ID arrays, start/end timestamps, and active state. Responses include
the calculated state `live`, `upcoming`, `expired`, or `inactive`.

### GET, PATCH, DELETE `/api/staff/discounts/promotions/{id}/`

Retrieves, partially updates, or deletes a promotion. Invalid schedules or
targets return `400`; missing records return `404`; PUT returns `405`.

### GET, POST `/api/staff/discounts/gift-cards/`

Lists masked cards or issues a new GHS gift card. POST accepts positive
`initial_balance`, optional `recipient_email` and future `expires_at`, and
`is_active`. The cryptographically generated full `code` is returned only in
the `201 Created` response. Django stores only its keyed hash and masked suffix.

### GET, PATCH `/api/staff/discounts/gift-cards/{id}/`

Retrieves or updates recipient email, expiry, or active state. Initial/current/
reserved balances and code identifiers are read-only. Deletion and PUT return
`405`; missing cards return `404`.

### GET `/api/staff/discounts/gift-cards/{id}/transactions/`

Returns paginated reservation, release, redemption, and refund-restoration
entries with checkout/order references, amounts, and timestamps.

Checkout quote and payment requests accept optional `gift_card_code`. Responses
separate `promotion_discount`, `coupon_discount`, `gift_card_discount`, and
`applied_promotions`. The best automatic percentage promotion applies per line,
then one coupon, then one gift card. Gift-card funds and coupon usage are
reserved during hosted checkout, released on failure/expiration, and redeemed
once after verified payment. A fully covered checkout is fulfilled as store
credit without contacting an external provider.

## Shipping management

All shipping-management endpoints require an authenticated active staff user.
Unauthenticated requests return `401`; customer accounts return `403`.

### GET `/api/staff/shipping/orders/`

Returns paginated processing, shipped, and delivered orders with customer,
destination, courier, tracking number, products, and status. Optional `status`
accepts `processing`, `shipped`, or `delivered`; invalid values return `400`.
Staff assign courier/tracking and advance delivery through the existing order
PATCH endpoint.

### GET, POST `/api/staff/shipping/methods/`

Lists or creates methods. POST accepts `name`, unique `code`, `kind`
(`standard`, `express`, or `pickup`), `estimated_days`, and `is_active`.

### GET, PATCH, DELETE `/api/staff/shipping/methods/{id}/`

Retrieves, partially updates, or deletes a method. Success returns `200` or
`204`; validation returns `400`; missing records return `404`; PUT returns `405`.

### GET, POST `/api/staff/shipping/zones/`

Lists or creates zones using `name`, arrays of nonblank `countries`, `regions`,
and `cities`, and `is_active`. Regions and cities may be empty.

### GET, PATCH, DELETE `/api/staff/shipping/zones/{id}/`

Retrieves, partially updates, or deletes one zone, returning `200` or `204`.
Validation returns `400`, missing records `404`, and PUT `405`.

### GET, POST `/api/staff/shipping/rates/`

Lists or creates rates using method and zone IDs, nonnegative `amount`, optional
nonnegative `free_shipping_threshold`, and `is_active`. A method/zone pair must
be unique. Creation returns `201`; invalid data returns `400`.

### GET, PATCH, DELETE `/api/staff/shipping/rates/{id}/`

Retrieves, partially updates, or deletes one rate. Success returns `200` or
`204`; missing records return `404`; PUT returns `405`.

Configured rates are staff reference data in this release. Checkout continues
using the store-wide shipping fee and threshold until a customer-facing method
and zone selection is added.

## Payments

### GET `/api/checkout/payment-methods/`

Returns configured hosted payment methods for an authenticated customer. No
keys or provider secrets are returned. Each result contains `provider`,
`method`, `label`, `description`, and `enabled`. Success is `200`; an
unauthenticated request returns `401`.

### POST `/api/checkout/payments/`

Creates a hosted Stripe or Paystack payment using the authenticated
customer's cart. The request contains the existing billing/address and optional
coupon fields plus `provider` and `method`. Valid pairs are Stripe/card,
The accepted choices are Stripe/card and Paystack/card. Paystack's hosted page
then lets the customer use an enabled card, Ghana Mobile Money, or bank transfer
channel. PayPal and store credit are not separate checkout choices. A gift card
may still reduce the payable amount before the selected provider is opened.

```json
{
  "provider": "paystack",
  "method": "mobile_money",
  "billing_name": "Alice Example",
  "billing_email": "alice@example.com",
  "address": "1 Main Street",
  "city": "Accra",
  "postal_code": "GA1",
  "country": "Ghana",
  "coupon_code": ""
}
```

Success returns `201 Created` with `id`, `checkout_url`, `provider`, and
`method`. Invalid combinations, an empty cart, unavailable stock, or an
unconfigured provider return field-level `400`; unauthenticated requests return
`401`. Totals are server-calculated. PayPal snapshots its configured GHS-to-USD
rate and USD charge amount.

### GET `/api/staff/payments/transactions/`

Returns active staff a paginated transaction list. Filters are `provider`,
`method`, `status`, `date_from`, `date_to`, `search`, and `page`. Search matches
provider references and public order numbers. Results include the public UUID,
order, provider/method, card brand when supplied by the provider, store and
provider amounts/currencies, conversion rate, refund data, and timestamps.

### GET `/api/staff/payments/methods/`

Returns every supported method with its safe configured/enabled state and local
transaction count. Credentials are never returned.

### GET `/api/staff/payments/refunds/`

Returns the same paginated staff refund history documented under Orders.

### GET `/api/staff/payments/reports/`

Returns internal gross revenue, refunded amount, net revenue, paid transaction
count, and total transaction count grouped by stored currency, plus counts by
provider. Optional `date_from` and `date_to` use ISO dates. Different currencies
are never added together. These figures are not provider payout settlements.

All `/api/staff/payments/` endpoints return `401` without authentication and
`403` for authenticated non-staff users.

### POST `/api/payments/paystack/webhook/`

Receives Paystack events. It is public but requires a valid
`X-Paystack-Signature`, validates checkout reference, currency, and amount, and
requires Paystack's transaction status to be `success`. When metadata includes a
`checkout_id`, it must match the stored checkout attempt. Successful replayed
events are idempotent and never create a second order or decrement stock twice.
Invalid signatures return `400`; accepted
events return `200`.

### POST `/api/payments/paypal/webhook/`

Receives PayPal events. It is public but verifies the transmission with PayPal
and the configured webhook ID before processing. Invalid or unconfigured
signatures return `400`; accepted events return `200`.

## Checkout and Stripe

These endpoints require session authentication except for the signed webhook.
Unsafe browser requests also require CSRF. Prices are calculated from database
values with `Decimal`; client totals are ignored.

After a verified paid checkout creates the order, the server sends one purchase
confirmation to the checkout billing email. It includes the public order number,
items, total, fulfillment status, and an authenticated order/invoice link. Stripe
webhook retries do not send duplicate messages. Email delivery failures are
logged and remain retryable without rolling back the paid order, stock changes,
coupon usage, invoice, or cart clearing.

### POST `/api/checkout/quote/`

Validates the cart and optional coupon without reserving it.

Request:

```json
{"coupon_code": "SAVE10"}
```

Success — `200 OK`:

```json
{
  "subtotal": "100.00",
  "discount": "10.00",
  "shipping": "0.00",
  "tax": "6.75",
  "total": "96.75",
  "currency": "USD"
}
```

Cart, stock, and coupon validation failures return `400 Bad Request` with
field-level errors.

### POST `/api/checkout/sessions/`

Snapshots the cart and address, reserves coupon usage, and creates a 30-minute
hosted Stripe Checkout Session. Store totals remain in GHS. When the connected
Stripe account cannot present GHS, the hosted session charges the USD equivalent
using the configured `STRIPE_GHS_TO_USD_RATE`; the provider amount and rate are
recorded on the payment transaction.

Request:

```json
{
  "billing_name": "Alice Example",
  "billing_email": "alice@example.com",
  "address": "1 Main Street",
  "city": "Accra",
  "postal_code": "10000",
  "country": "Ghana",
  "coupon_code": "SAVE10"
}
```

Success — `201 Created`:

```json
{
  "id": "87aa5239-c45c-42d4-a176-664fa176e9eb",
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

Invalid input or Stripe initialization returns `400`.

### GET `/api/checkout/sessions/{uuid}/`

Returns an ownership-scoped status for polling. It accepts no body. The signed
webhook remains the primary fulfillment path. If a successful Stripe redirect
arrives before its webhook, polling securely retrieves the checkout's stored
Stripe Session server-side and performs the same idempotent fulfillment once
Stripe reports the payment as paid.

Success — `200 OK`:

```json
{
  "id": "87aa5239-c45c-42d4-a176-664fa176e9eb",
  "status": "fulfilled",
  "subtotal": "100.00",
  "discount": "10.00",
  "shipping": "0.00",
  "tax": "6.75",
  "total": "96.75",
  "currency": "USD",
  "order_id": 42,
  "invoice": {
    "id": "16b20c65-7947-4e75-88c8-57eb36afe321",
    "invoice_number": "INV-2026-000001",
    "status": "paid",
    "download_url": "/api/invoices/16b20c65-7947-4e75-88c8-57eb36afe321/download/"
  },
  "error_message": ""
}
```

Statuses are `created`, `paid`, `fulfilled`, `expired`, `refund_pending`,
`refunded`, `refund_failed`, and `failed`. Inaccessible UUIDs return `404`.

### POST `/api/payments/stripe/webhook/`

Receives Stripe events without session authentication or CSRF. It requires a
valid `Stripe-Signature` over the raw request body. Valid handled and duplicate
events return an empty `200 OK`. Invalid signatures return `400`:

```json
{"detail": "Invalid Stripe signature."}
```

Paid completions atomically recheck stock and create the order once. Unavailable
stock preserves the cart and triggers an idempotent refund. Expired sessions
release coupon reservations.

## Staff settings

All settings endpoints require an authenticated session and CSRF protection for
unsafe methods. Store and system settings require either a superuser or the
`orders.manage_store_settings` permission. User, role, and permission endpoints
are superuser-only. Ordinary staff receive `403`; unauthenticated users receive
`401`. `PUT` is unsupported.

### GET/PATCH `/api/staff/settings/store/`

Returns or partially updates the singleton store configuration. `PATCH` accepts
JSON or multipart form data. The optional logo must be JPEG, PNG, or WebP and no
larger than 5 MB. Tax rate is a decimal from `0` through `1`; changes apply only
to new checkout calculations.

```json
{
  "store_name": "ECCO Store",
  "logo": "/media/store/logo.webp",
  "address": "1 Main Street, Accra",
  "phone": "+233200000000",
  "email": "store@example.com",
  "tax_label": "vat",
  "tax_rate": "0.07500",
  "send_order_emails": true,
  "send_invoice_emails": true,
  "updated_at": "2026-08-12T12:00:00Z"
}
```

Successful `GET` and `PATCH` return `200`. Invalid fields, tax values, email, or
logo uploads return field-level `400` errors.

### GET `/api/staff/settings/system/`

Returns safe configuration status for payment providers, SMTP, session/password
security, currency, and unsupported integrations. It accepts no parameters or
body. Success is `200`. Secret keys, webhook secrets, SMTP passwords, and raw
environment values are never returned.

```json
{
  "can_manage_users": true,
  "store_currency": "GHS",
  "payments": [{"provider": "stripe", "label": "Stripe", "configured": true}],
  "email": {"backend": "EmailBackend", "host": "smtp.gmail.com", "port": 587, "tls": true, "configured": true},
  "security": {"password_validators": ["MinimumLengthValidator"], "session_timeout_seconds": 28800, "two_factor_authentication": false, "login_history": false, "api_keys": false}
}
```

### GET/POST `/api/staff/settings/users/`

Lists staff and administrators or creates a staff invitation. `GET` is paginated
and accepts `page`. Creation requires unique `username`, valid nonblank `email`,
and optional `role_ids`. The account receives an unusable password and a
single-use password-setup email.

```json
{"username": "warehouse", "email": "warehouse@example.com", "role_ids": [2]}
```

Success is `200` for lists and `201` for creation. The creation response includes
safe user fields plus `invitation_sent`. Validation and unknown role errors
return `400`; mail failure does not expose internal SMTP details.

### GET/PATCH `/api/staff/settings/users/{id}/`

Returns or updates an existing staff account. Editable fields are username,
email, active state, and `role_ids`. Superuser status is always read-only. Users
cannot deactivate themselves or change their own roles. Success is `200`; invalid
changes return `400`, and missing staff accounts return `404`.

### GET/POST `/api/staff/settings/roles/`

Lists roles or creates one with `name` and optional allowlisted
`permission_ids`. Lists accept `page`; creation returns `201`. Duplicate names,
unknown IDs, and permissions outside the ecommerce allowlist return `400`.

### GET/PATCH/DELETE `/api/staff/settings/roles/{id}/`

Retrieves, renames, changes allowlisted permissions, or deletes an unused role.
Successful reads/updates return `200`; deletion returns `204`. A role assigned to
any user cannot be deleted and returns `400`. Missing roles return `404`.

### GET `/api/staff/settings/roles/permissions/`

Returns `{"results": [...]}` containing the safe ID, name, codename, and app
label of permissions that may be assigned to staff roles. It accepts no body or
parameters and returns `200`.

## Invoices

Invoice endpoints require session authentication and invoice ownership. PDFs use
private storage and are never served through `/media/`.

### GET `/api/invoices/{uuid}/`

Returns invoice metadata with invoice number, status, issue date, monetary
breakdown, currency, PDF generation date, and download URL. It accepts no body.
Success returns `200 OK`; another user's or missing invoice returns `404`.

### GET `/api/invoices/{uuid}/download/`

Streams the owned A5 invoice with `Content-Type: application/pdf` and an
attachment filename based on the invoice number. If necessary, Django safely
regenerates the PDF from stored order snapshots. Success returns `200 OK`;
another user's or missing invoice returns `404`.
