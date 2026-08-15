const STORAGE_KEY = 'ecco-recently-viewed';
const MAX_ITEMS = 8;

export function getRecentlyViewed() {
    try {
        const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
        return Array.isArray(value) ? value.filter((slug) => typeof slug === 'string') : [];
    }
    catch {
        return [];
    }
}

export function rememberProduct(slug) {
    if (!slug)
        return;
    const slugs = [slug, ...getRecentlyViewed().filter((item) => item !== slug)].slice(0, MAX_ITEMS);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(slugs));
}
