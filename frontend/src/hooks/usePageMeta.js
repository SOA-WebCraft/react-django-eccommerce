import { useEffect } from 'react';

const DEFAULT_TITLE = 'ECCO | Modern technology, thoughtfully selected';
const DEFAULT_DESCRIPTION = 'Shop carefully selected smartphones, laptops, tablets, smartwatches, and accessories at ECCO.';

function upsertMeta(selector, attributes) {
    let element = document.head.querySelector(selector);
    if (!element) {
        element = document.createElement('meta');
        document.head.appendChild(element);
    }
    Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
}

export function usePageMeta({ title, description = DEFAULT_DESCRIPTION, image, type = 'website', schema } = {}) {
    const schemaJson = schema ? JSON.stringify(schema) : '';
    useEffect(() => {
        const pageTitle = title ? `${title} | ECCO` : DEFAULT_TITLE;
        const canonicalUrl = `${window.location.origin}${window.location.pathname}`;
        document.title = pageTitle;
        upsertMeta('meta[name="description"]', { name: 'description', content: description });
        upsertMeta('meta[property="og:title"]', { property: 'og:title', content: pageTitle });
        upsertMeta('meta[property="og:description"]', { property: 'og:description', content: description });
        upsertMeta('meta[property="og:type"]', { property: 'og:type', content: type });
        upsertMeta('meta[property="og:url"]', { property: 'og:url', content: canonicalUrl });
        upsertMeta('meta[name="twitter:card"]', { name: 'twitter:card', content: image ? 'summary_large_image' : 'summary' });
        if (image) {
            upsertMeta('meta[property="og:image"]', { property: 'og:image', content: image });
            upsertMeta('meta[name="twitter:image"]', { name: 'twitter:image', content: image });
        }
        else {
            document.head.querySelector('meta[property="og:image"]')?.remove();
            document.head.querySelector('meta[name="twitter:image"]')?.remove();
        }
        let canonical = document.head.querySelector('link[rel="canonical"]');
        if (!canonical) {
            canonical = document.createElement('link');
            canonical.rel = 'canonical';
            document.head.appendChild(canonical);
        }
        canonical.href = canonicalUrl;
        document.getElementById('ecco-structured-data')?.remove();
        if (schemaJson) {
            const script = document.createElement('script');
            script.id = 'ecco-structured-data';
            script.type = 'application/ld+json';
            script.text = schemaJson;
            document.head.appendChild(script);
        }
        return () => document.getElementById('ecco-structured-data')?.remove();
    }, [description, image, schemaJson, title, type]);
}
