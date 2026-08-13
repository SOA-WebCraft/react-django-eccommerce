import { toast } from 'react-toastify';
function normalizeApiBase(value) {
    const base = (value || '/api').trim();
    if (/^https?:\/\//i.test(base))
        return base.replace(/\/+$/, '');
    return `/${base.replace(/^\/+|\/+$/g, '')}`;
}
export const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE_URL);
let unauthorizedHandler = null;

export function onUnauthorized(handler) {
    unauthorizedHandler = handler;
}
export class ApiError extends Error {
    status;
    data;
    constructor(status, data) {
        super(extractErrorMessage(data, status));
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }
}
function flatten(value) {
    if (typeof value === 'string')
        return [value];
    if (Array.isArray(value))
        return value.flatMap(flatten);
    if (value && typeof value === 'object') {
        return Object.values(value).flatMap(flatten);
    }
    return [];
}
function showApiErrors(data, status) {
    const messages = [...new Set(flatten(data))];
    if (messages.length) {
        messages.forEach((message) => toast.error(message, { toastId: `api-${status}-${message}` }));
        return;
    }
    const message = extractErrorMessage(data, status);
    toast.error(message, { toastId: `api-${status}-${message}` });
}
export function extractErrorMessage(data, status = 0) {
    const messages = flatten(data);
    if (messages.length)
        return messages[0];
    if (status === 403)
        return 'You do not have permission to perform this action.';
    if (status === 404)
        return 'The requested resource was not found.';
    if (status >= 500)
        return 'The server could not complete the request.';
    return 'Something went wrong. Please try again.';
}
export function fieldErrors(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data))
        return {};
    return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, flatten(value).join(' ')]));
}
async function parseResponse(response) {
    if (response.status === 204)
        return null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json'))
        return response.json();
    const text = await response.text();
    return text ? { detail: text } : {};
}
function getCookie(name) {
    const prefix = `${name}=`;
    const cookie = document.cookie
        .split(';')
        .map((value) => value.trim())
        .find((value) => value.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : '';
}

async function ensureCsrfCookie() {
    if (getCookie('csrftoken'))
        return;
    const response = await fetch(`${API_BASE}/users/csrf/`, {
        credentials: 'include',
    });
    if (!response.ok)
        throw new ApiError(response.status, await parseResponse(response));
}

export async function apiRequest(path, options = {}, showErrors = true) {
    const headers = new Headers(options.headers);
    const method = (options.method || 'GET').toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        await ensureCsrfCookie();
        headers.set('X-CSRFToken', getCookie('csrftoken'));
    }
    if (options.body && !(options.body instanceof FormData)) {
        headers.set('Content-Type', 'application/json');
    }
    let response;
    try {
        response = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
            credentials: 'include',
        });
    }
    catch {
        const error = new ApiError(0, {
            detail: 'Unable to reach the store. Check your connection and try again.',
        });
        if (showErrors)
            showApiErrors(error.data, error.status);
        throw error;
    }
    const data = await parseResponse(response);
    if (!response.ok) {
        const error = new ApiError(response.status, (data || {}));
        if (response.status === 401)
            unauthorizedHandler?.();
        if (showErrors)
            showApiErrors(error.data, error.status);
        throw error;
    }
    return data;
}
export function queryString(values) {
    const params = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => {
        if (value !== undefined && value !== '')
            params.set(key, String(value));
    });
    const query = params.toString();
    return query ? `?${query}` : '';
}
