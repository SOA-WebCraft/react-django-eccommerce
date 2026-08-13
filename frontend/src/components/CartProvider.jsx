import { useCallback, useEffect, useMemo, useState } from 'react';
import { cartApi } from '../api/services';
import { useAuth } from '../hooks/useAuth';
import { CartContext } from './CartContext';

export function CartProvider({ children }) {
    const { isAuthenticated } = useAuth();
    const [cart, setCart] = useState(null);
    const [loading, setLoading] = useState(false);
    const refresh = useCallback(async () => {
        if (!isAuthenticated) {
            setCart(null);
            return;
        }
        setLoading(true);
        try {
            setCart(await cartApi.get());
        }
        finally {
            setLoading(false);
        }
    }, [isAuthenticated]);
    useEffect(() => {
        void refresh();
    }, [refresh]);
    const clearLocal = useCallback(() => setCart(null), []);
    const value = useMemo(() => ({
        cart,
        loading,
        count: cart?.items.reduce((sum, item) => sum + item.quantity, 0) ?? 0,
        refresh,
        async add(product, quantity) {
            await cartApi.add(product, quantity);
            await refresh();
        },
        async adjust(item, operation) {
            await cartApi.adjust(item, operation);
            await refresh();
        },
        async remove(item) {
            await cartApi.remove(item);
            await refresh();
        },
        clearLocal,
    }), [cart, clearLocal, loading, refresh]);
    return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}
