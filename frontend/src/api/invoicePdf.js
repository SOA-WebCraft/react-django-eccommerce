const inFlightRequests = new Map();

async function invoiceError(response) {
    try {
        const data = await response.json();
        if (typeof data?.detail === 'string')
            return data.detail;
    }
    catch {
        // The fallback below covers non-JSON error responses.
    }
    return 'Unable to load the invoice PDF.';
}

export function acquireInvoicePdf(url) {
    const existing = inFlightRequests.get(url);
    if (existing) {
        existing.consumers += 1;
        if (existing.abortTimer) {
            window.clearTimeout(existing.abortTimer);
            existing.abortTimer = null;
        }
        return {
            promise: existing.promise,
            release: () => releaseRequest(url, existing),
        };
    }

    const controller = new AbortController();
    const entry = {
        abortTimer: null,
        consumers: 1,
        controller,
        promise: null,
    };
    entry.promise = fetch(url, {
        credentials: 'include',
        signal: controller.signal,
    }).then(async (response) => {
        if (!response.ok)
            throw new Error(await invoiceError(response));
        const blob = await response.blob();
        if (!blob.type.toLowerCase().includes('pdf'))
            throw new Error('The invoice response is not a PDF.');
        return blob;
    }).finally(() => {
        if (inFlightRequests.get(url) === entry)
            inFlightRequests.delete(url);
    });
    inFlightRequests.set(url, entry);

    return {
        promise: entry.promise,
        release: () => releaseRequest(url, entry),
    };
}

function releaseRequest(url, entry) {
    entry.consumers = Math.max(0, entry.consumers - 1);
    if (entry.consumers || entry.abortTimer)
        return;
    entry.abortTimer = window.setTimeout(() => {
        if (entry.consumers)
            return;
        entry.controller.abort();
        if (inFlightRequests.get(url) === entry)
            inFlightRequests.delete(url);
    }, 0);
}
