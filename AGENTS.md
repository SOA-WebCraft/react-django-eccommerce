AGENTS.md

Mission

Build and maintain a minimal ecommerce REST API with Django and Django REST Framework.

Optimize for simplicity, correctness, secure defaults, clear API behavior, and small changes. Avoid unnecessary abstractions, dependencies, services, and features.

Stack

Python

Django

Django REST Framework

SQLite for local development

pytest or Django's test framework

Token or JWT authentication only when required

Scope

Core resources:

Products

Categories

Users

Carts and cart items

Orders and order items

Do not add payments, shipping integrations, coupons, reviews, wishlists, analytics, or background jobs unless explicitly requested.

Structure

Use conventional Django apps such as:

users

catalog

cart

orders

Place:

Data rules in models

Input validation and representation in serializers

HTTP behavior in views or viewsets

Reusable complex business logic in small service functions

Do not introduce a repository pattern.

API Conventions

Use plural RESTful URLs with trailing slashes.

Examples:

GET /api/products/

POST /api/products/

GET /api/products/{id}/

PATCH /api/products/{id}/

DELETE /api/products/{id}/

GET /api/categories/

GET /api/cart/

POST /api/cart/items/

PATCH /api/cart/items/{id}/

DELETE /api/cart/items/{id}/

POST /api/orders/

GET /api/orders/

GET /api/orders/{id}/

Use standard HTTP status codes. Never expose stack traces, internal exceptions, secrets, or sensitive fields.

Endpoint Documentation

Every endpoint must be documented in a Markdown file named api_docs.md.

Update api_docs.md whenever an endpoint is added, changed, or removed. For each endpoint include:

Method and URL

Purpose

Authentication and permissions

Query or path parameters

Request body example

Success response example

Error response examples

Relevant status codes

An endpoint change is incomplete until api_docs.md is updated.

Models

Keep models small and explicit. Use database constraints for important invariants.

Recommended fields:

Product

id

name

slug

description

price

stock_quantity

is_active

category

created_at

updated_at

Category

id

name

slug

Cart

id

user

created_at

updated_at

CartItem

id

cart

product

quantity

Order

id

user

status

total

created_at

updated_at

OrderItem

id

order

product

product_name

unit_price

quantity

line_total

Use DecimalField for money. Never use floating-point prices or totals.

Store product name and price snapshots on order items so later product changes do not alter past orders.

Validation

Validate all client input.

Required rules:

Price must be zero or greater

Stock must be zero or greater

Cart quantity must be greater than zero

Only active products may be added to a cart

Cart quantity must not exceed available stock

An order cannot be created from an empty cart

Users may access only their own carts and orders

Return clear field-level errors.

Authentication and Permissions

Product and category reads may be public.

Require authentication for carts, order creation, order history, and user-specific resources.

Use DRF permission classes. Derive ownership from request.user; never trust a client-supplied user ID.

Order Creation

Order creation must use transaction.atomic().

Process:

Validate the cart.

Re-check or safely lock product stock.

Create the order.

Create order items from product snapshots.

Decrease stock.

Calculate and store the server-side total.

Clear the cart only after success.

Never trust prices or totals submitted by the client.

Serializers

Keep serializers explicit.

Mark ownership, timestamps, calculated values, and totals as read-only.

Do not expose passwords, tokens, internal permissions, or unnecessary user data.

Avoid deeply nested writable serializers.

Queries and Performance

Prevent obvious N+1 queries with:

select_related() for foreign keys

prefetch_related() for collections

Paginate product and order lists.

Add indexes only for fields frequently used in filters, sorting, or lookups.

Prefer readable queries over premature optimization.

Filtering and Ordering

Support only useful filters, such as:

Product category

Product active status

Product price range

Product name search

Order status

Allow ordering only by approved fields. Never pass unchecked client values into raw SQL or unrestricted ordering.

Errors

Prefer DRF's standard error structure.

Use status codes consistently:

200 OK

201 Created

204 No Content

400 Bad Request

401 Unauthorized

403 Forbidden

404 Not Found

409 Conflict when appropriate

Never return 200 OK for a failed operation.

Tests

Every behavior change must include tests.

Cover:

Successful requests

Validation failures

Authentication

Permissions and ownership

Stock limits

Empty-cart order rejection

Total calculations

Atomic order creation

Response shapes

Prefer focused API tests over excessive mocking. Tests must not depend on execution order.

Migrations

Create migrations for every model change.

Do not edit already-applied migrations unless explicitly required.

Review migrations for accidental destructive operations.

Style

Follow PEP 8 and Django conventions.

Use clear names, small functions, and explicit code.

Do not leave dead code, commented-out code, debug prints, or unused imports.

Add comments only when the reason is not clear from the code.

Dependencies

Add a dependency only when Django, DRF, or the standard library cannot reasonably solve the problem.

Follow the project's existing dependency pinning strategy.

Security

Never commit secrets, API keys, production credentials, tokens, or real customer data.

Use environment variables for configuration.

Validate file uploads if uploads are introduced.

Avoid raw SQL unless necessary and reviewed.

Definition of Done

A change is complete only when:

The implementation is minimal and correct

Validation and permissions are enforced

Tests pass

Required migrations are included

api_docs.md reflects every endpoint change

No secrets or debug artifacts remain

Supported Python and Django versions remain compatible