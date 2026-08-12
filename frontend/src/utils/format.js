export const formatPrice = (value, currency = 'GHS') => new Intl.NumberFormat('en-GH', {
    style: 'currency',
    currency,
}).format(Number(value));
export const formatDate = (value) => new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
}).format(new Date(value));
