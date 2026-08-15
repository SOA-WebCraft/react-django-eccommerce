import { useMemo, useState } from 'react';
import { CompareContext } from './CompareContext';

const STORAGE_KEY = 'ecco-product-comparison';
const MAX_PRODUCTS = 3;

function initialSlugs() {
    try {
        const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
        return Array.isArray(value) ? value.filter((slug) => typeof slug === 'string').slice(0, MAX_PRODUCTS) : [];
    }
    catch {
        return [];
    }
}

export function CompareProvider({ children }) {
    const [slugs, setSlugs] = useState(initialSlugs);
    const save = (next) => {
        setSlugs(next);
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    };
    const value = useMemo(() => ({
        slugs,
        count: slugs.length,
        has: (slug) => slugs.includes(slug),
        toggle: (slug) => {
            if (slugs.includes(slug)) {
                save(slugs.filter((item) => item !== slug));
                return false;
            }
            if (slugs.length >= MAX_PRODUCTS)
                throw new Error('You can compare up to three products at a time.');
            save([...slugs, slug]);
            return true;
        },
        remove: (slug) => save(slugs.filter((item) => item !== slug)),
        clear: () => save([]),
    }), [slugs]);
    return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}
