import { useEffect, useState } from 'react';
import { orderApi } from '../api/services';
export function useOrder(id) {
    const [order, setOrder] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    useEffect(() => {
        orderApi
            .detail(id)
            .then(setOrder)
            .catch((reason) => setError(reason.message))
            .finally(() => setLoading(false));
    }, [id]);
    return { order, setOrder, loading, error, setError };
}
