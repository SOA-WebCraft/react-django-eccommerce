import { useCallback, useEffect, useMemo, useState } from 'react';
import { wishlistApi } from '../api/services';
import { useAuth } from '../hooks/useAuth';
import { WishlistContext } from './WishlistContext';

export function WishlistProvider({ children }) {
    const { isAuthenticated } = useAuth();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(false);
    const refresh = useCallback(async () => {
        if (!isAuthenticated) {
            setItems([]);
            return;
        }
        setLoading(true);
        try {
            setItems(await wishlistApi.list());
        }
        catch {
            setItems([]);
        }
        finally {
            setLoading(false);
        }
    }, [isAuthenticated]);
    useEffect(() => {
        void refresh();
    }, [refresh]);
    const value = useMemo(() => ({
        items,
        loading,
        count: items.length,
        has(productId) {
            return items.some((item) => item.product === productId);
        },
        async toggle(productId) {
            const existing = items.find((item) => item.product === productId);
            if (existing)
                await wishlistApi.remove(existing.id);
            else
                await wishlistApi.add(productId);
            await refresh();
            return !existing;
        },
        refresh,
        clearLocal: () => setItems([]),
    }), [items, loading, refresh]);
    return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>;
}
