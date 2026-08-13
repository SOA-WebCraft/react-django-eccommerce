import { API_BASE, apiRequest, queryString } from './client';
export const authApi = {
    csrf: () => apiRequest('/users/csrf/'),
    socialProviders: () => apiRequest('/users/social-providers/', {}, false),
    socialLoginUrl: (provider, next = '/account') => `${API_BASE}/users/social-login/${provider}/?${new URLSearchParams({ next })}`,
    login: (username, password) => apiRequest('/users/login/', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
    }),
    register: (body) => apiRequest('/users/register/', {
        method: 'POST',
        body: JSON.stringify(body),
    }),
    logout: () => apiRequest('/users/logout/', { method: 'POST' }, false),
    requestPasswordReset: (email) => apiRequest('/users/password-reset/', {
        method: 'POST',
        body: JSON.stringify({ email }),
    }),
    confirmPasswordReset: (body) => apiRequest('/users/password-reset/confirm/', {
        method: 'POST',
        body: JSON.stringify(body),
    }),
    updateProfile: (body) => apiRequest('/users/me/', {
        method: 'PATCH',
        body: JSON.stringify(body),
    }),
    me: (showErrors = true) => apiRequest('/users/me/', {}, showErrors),
};
export const catalogApi = {
    categories: () => apiRequest('/categories/'),
    products: (filters = {}) => apiRequest(`/products/${queryString(filters)}`),
    product: (slug) => apiRequest(`/products/${slug}/`),
    createProduct: (body) => apiRequest('/products/', { method: 'POST', body }),
    updateProduct: (slug, body) => apiRequest(`/products/${slug}/`, { method: 'PATCH', body }),
    deleteProduct: (slug) => apiRequest(`/products/${slug}/`, { method: 'DELETE' }),
};
export const cartApi = {
    get: () => apiRequest('/cart/', { cache: 'no-store' }),
    add: (product, quantity) => apiRequest('/cart/items/', {
        method: 'POST',
        body: JSON.stringify({ product, quantity }),
    }),
    adjust: (id, operation) => apiRequest(`/cart/items/${id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ operation }),
    }),
    remove: (id) => apiRequest(`/cart/items/${id}/`, { method: 'DELETE' }),
};
export const orderApi = {
    list: (page = 1, status) => apiRequest(`/orders/${queryString({ page, status: status || undefined })}`),
    detail: (id) => apiRequest(`/orders/${id}/`),
    updateStatus: (id, status, extra = {}) => apiRequest(`/orders/${id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ status, ...extra }),
    }),
    requestReturn: (id, reason) => apiRequest(`/orders/${id}/returns/`, { method: 'POST', body: JSON.stringify({ reason }) }),
    returns: (page = 1, status) => apiRequest(`/staff/returns/${queryString({ page, status: status || undefined })}`),
    updateReturn: (id, body) => apiRequest(`/staff/returns/${id}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    refunds: (page = 1) => apiRequest(`/staff/refunds/${queryString({ page })}`),
    refund: (id) => apiRequest(`/staff/orders/${id}/refund/`, { method: 'POST', body: JSON.stringify({}) }),
    sendEmail: (id) => apiRequest(`/staff/orders/${id}/send-email/`, { method: 'POST', body: JSON.stringify({}) }),
};
export const analyticsApi = {
    get: () => apiRequest('/staff/analytics/', { cache: 'no-store' }),
};
export const customerApi = {
    list: (filters = {}) => apiRequest(`/staff/customers/${queryString(filters)}`),
    detail: (id) => apiRequest(`/staff/customers/${id}/`),
};
export const inventoryApi = {
    stock: (filters = {}) => apiRequest(`/staff/inventory/stock/${queryString(filters)}`, { cache: 'no-store' }),
    adjust: (body) => apiRequest('/staff/inventory/adjustments/', { method: 'POST', body: JSON.stringify(body) }),
    movements: (filters = {}) => apiRequest(`/staff/inventory/movements/${queryString(filters)}`),
    suppliers: (filters = {}) => apiRequest(`/staff/inventory/suppliers/${queryString(filters)}`),
    createSupplier: (body) => apiRequest('/staff/inventory/suppliers/', { method: 'POST', body: JSON.stringify(body) }),
    updateSupplier: (id, body) => apiRequest(`/staff/inventory/suppliers/${id}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteSupplier: (id) => apiRequest(`/staff/inventory/suppliers/${id}/`, { method: 'DELETE' }),
    purchaseOrders: (filters = {}) => apiRequest(`/staff/inventory/purchase-orders/${queryString(filters)}`),
    createPurchaseOrder: (body) => apiRequest('/staff/inventory/purchase-orders/', { method: 'POST', body: JSON.stringify(body) }),
    receivePurchaseOrder: (id) => apiRequest(`/staff/inventory/purchase-orders/${id}/receive/`, { method: 'POST', body: JSON.stringify({}) }),
    cancelPurchaseOrder: (id) => apiRequest(`/staff/inventory/purchase-orders/${id}/cancel/`, { method: 'POST', body: JSON.stringify({}) }),
};
export const checkoutApi = {
    quote: (couponCode = '', giftCardCode = '') => apiRequest('/checkout/quote/', {
        method: 'POST',
        body: JSON.stringify({ coupon_code: couponCode, gift_card_code: giftCardCode }),
    }),
    createSession: (body) => apiRequest('/checkout/sessions/', {
        method: 'POST',
        body: JSON.stringify(body),
    }),
    status: (id) => apiRequest(`/checkout/sessions/${id}/`),
    methods: () => apiRequest('/checkout/payment-methods/'),
    createPayment: (body) => apiRequest('/checkout/payments/', {
        method: 'POST', body: JSON.stringify(body),
    }),
};
export const paymentApi = {
    transactions: (filters = {}) => apiRequest(`/staff/payments/transactions/${queryString(filters)}`),
    methods: () => apiRequest('/staff/payments/methods/'),
    refunds: (page = 1) => apiRequest(`/staff/payments/refunds/${queryString({ page })}`),
    reports: (filters = {}) => apiRequest(`/staff/payments/reports/${queryString(filters)}`),
};
export const shippingApi = {
    orders: (filters = {}) => apiRequest(`/staff/shipping/orders/${queryString(filters)}`),
    methods: () => apiRequest('/staff/shipping/methods/'),
    createMethod: (body) => apiRequest('/staff/shipping/methods/', { method: 'POST', body: JSON.stringify(body) }),
    updateMethod: (id, body) => apiRequest(`/staff/shipping/methods/${id}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteMethod: (id) => apiRequest(`/staff/shipping/methods/${id}/`, { method: 'DELETE' }),
    zones: () => apiRequest('/staff/shipping/zones/'),
    createZone: (body) => apiRequest('/staff/shipping/zones/', { method: 'POST', body: JSON.stringify(body) }),
    updateZone: (id, body) => apiRequest(`/staff/shipping/zones/${id}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteZone: (id) => apiRequest(`/staff/shipping/zones/${id}/`, { method: 'DELETE' }),
    rates: () => apiRequest('/staff/shipping/rates/'),
    createRate: (body) => apiRequest('/staff/shipping/rates/', { method: 'POST', body: JSON.stringify(body) }),
    updateRate: (id, body) => apiRequest(`/staff/shipping/rates/${id}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteRate: (id) => apiRequest(`/staff/shipping/rates/${id}/`, { method: 'DELETE' }),
};
export const discountApi = {
    coupons: () => apiRequest('/staff/discounts/coupons/'),
    createCoupon: (body) => apiRequest('/staff/discounts/coupons/', { method: 'POST', body: JSON.stringify(body) }),
    updateCoupon: (id, body) => apiRequest(`/staff/discounts/coupons/${id}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    deleteCoupon: (id) => apiRequest(`/staff/discounts/coupons/${id}/`, { method: 'DELETE' }),
    promotions: () => apiRequest('/staff/discounts/promotions/'),
    createPromotion: (body) => apiRequest('/staff/discounts/promotions/', { method: 'POST', body: JSON.stringify(body) }),
    updatePromotion: (id, body) => apiRequest(`/staff/discounts/promotions/${id}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    deletePromotion: (id) => apiRequest(`/staff/discounts/promotions/${id}/`, { method: 'DELETE' }),
    giftCards: () => apiRequest('/staff/discounts/gift-cards/'),
    createGiftCard: (body) => apiRequest('/staff/discounts/gift-cards/', { method: 'POST', body: JSON.stringify(body) }),
    updateGiftCard: (id, body) => apiRequest(`/staff/discounts/gift-cards/${id}/`, { method: 'PATCH', body: JSON.stringify(body) }),
    giftCardTransactions: (id) => apiRequest(`/staff/discounts/gift-cards/${id}/transactions/`),
};
export const settingsApi = {
    store: () => apiRequest('/staff/settings/store/'),
    updateStore: (body) => apiRequest('/staff/settings/store/', {
        method: 'PATCH', body,
    }),
    system: () => apiRequest('/staff/settings/system/'),
    users: () => apiRequest('/staff/settings/users/'),
    createUser: (body) => apiRequest('/staff/settings/users/', {
        method: 'POST', body: JSON.stringify(body),
    }),
    updateUser: (id, body) => apiRequest(`/staff/settings/users/${id}/`, {
        method: 'PATCH', body: JSON.stringify(body),
    }),
    roles: () => apiRequest('/staff/settings/roles/'),
    permissions: () => apiRequest('/staff/settings/roles/permissions/'),
    createRole: (body) => apiRequest('/staff/settings/roles/', {
        method: 'POST', body: JSON.stringify(body),
    }),
    updateRole: (id, body) => apiRequest(`/staff/settings/roles/${id}/`, {
        method: 'PATCH', body: JSON.stringify(body),
    }),
    deleteRole: (id) => apiRequest(`/staff/settings/roles/${id}/`, {
        method: 'DELETE',
    }),
};
export const invoiceApi = {
    detail: (id) => apiRequest(`/invoices/${id}/`),
};
