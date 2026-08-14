import { useCallback, useEffect, useRef, useState } from 'react';
import { analyticsApi } from '../api/services';

function websocketUrl(value, ticket) {
    const base = value.startsWith('/')
        ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${value}`
        : value;
    const url = new URL(base);
    url.searchParams.set('ticket', ticket);
    return url.toString();
}

const emptySummary = {
    total_revenue: '0.00', paid_orders: 0, total_orders: 0, customers: 0,
};
const emptyStatistics = {
    period_days: 30, revenue: '0.00', revenue_change_percent: 0,
    paid_orders: 0, paid_orders_change_percent: 0,
    average_order_value: '0.00', units_sold: 0, unique_customers: 0,
    repeat_customer_rate: '0.0', new_customers: 0,
};
const emptyFinancials = {
    gross_sales: '0.00', discounts: '0.00', shipping: '0.00', tax: '0.00',
    refunds: '0.00', net_revenue: '0.00',
};
const emptyCheckoutPerformance = {
    started: 0, completed: 0, abandoned_or_failed: 0, completion_rate: '0.0',
};
const emptyInventoryHealth = {
    active_products: 0, low_stock: 0, out_of_stock: 0,
    units_available: 0, retail_value: '0.00',
};

function normalizeAnalytics(snapshot = {}) {
    return {
        ...snapshot,
        summary: { ...emptySummary, ...snapshot.summary },
        statistics: { ...emptyStatistics, ...snapshot.statistics },
        financials: { ...emptyFinancials, ...snapshot.financials },
        checkout_performance: {
            ...emptyCheckoutPerformance,
            ...snapshot.checkout_performance,
        },
        inventory_health: {
            ...emptyInventoryHealth,
            ...snapshot.inventory_health,
        },
        orders_by_status: snapshot.orders_by_status || [],
        daily_sales: snapshot.daily_sales || [],
        top_products: snapshot.top_products || [],
        sales_by_category: snapshot.sales_by_category || [],
        sales_by_payment_method: snapshot.sales_by_payment_method || [],
        low_stock_products: snapshot.low_stock_products || [],
    };
}

export function useAnalyticsStream(enabled) {
    const [analytics, setAnalytics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [connection, setConnection] = useState('connecting');
    const [lastUpdated, setLastUpdated] = useState(null);
    const socketRef = useRef(null);

    const loadSnapshot = useCallback(async () => {
        try {
            const data = await analyticsApi.get();
            setAnalytics(normalizeAnalytics(data));
            setLastUpdated(new Date());
            setError('');
        }
        catch (reason) {
            setError(reason.message);
        }
        finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (!enabled)
            return;
        void loadSnapshot();
    }, [enabled, loadSnapshot]);

    useEffect(() => {
        if (!enabled)
            return;
        let active = true;
        let retryTimer;
        let retryCount = 0;

        const connect = async () => {
            setConnection(retryCount ? 'reconnecting' : 'connecting');
            try {
                const access = await analyticsApi.socketTicket();
                if (!active)
                    return;
                const socket = new WebSocket(websocketUrl(
                    access.websocket_url,
                    access.ticket,
                ));
                socketRef.current = socket;
                socket.addEventListener('open', () => {
                    if (!active)
                        return;
                    retryCount = 0;
                    setConnection('live');
                    setError('');
                });
                socket.addEventListener('message', (event) => {
                    if (!active)
                        return;
                    try {
                        const message = JSON.parse(event.data);
                        if (message.type !== 'analytics.snapshot')
                            return;
                        setAnalytics(normalizeAnalytics(message.data));
                        setLastUpdated(new Date(message.sent_at));
                        setLoading(false);
                    }
                    catch {
                        setError('A live analytics update could not be read.');
                    }
                });
                socket.addEventListener('close', () => {
                    if (!active)
                        return;
                    socketRef.current = null;
                    setConnection('reconnecting');
                    retryCount += 1;
                    retryTimer = window.setTimeout(
                        connect,
                        Math.min(30000, 1000 * 2 ** Math.min(retryCount, 5)),
                    );
                });
                socket.addEventListener('error', () => {
                    if (active)
                        setConnection('reconnecting');
                });
            }
            catch (reason) {
                if (!active)
                    return;
                setConnection('fallback');
                setError(reason.message);
                retryCount += 1;
                retryTimer = window.setTimeout(
                    connect,
                    Math.min(30000, 1000 * 2 ** Math.min(retryCount, 5)),
                );
            }
        };
        void connect();
        const fallbackTimer = window.setInterval(() => {
            if (socketRef.current?.readyState !== WebSocket.OPEN)
                void loadSnapshot();
        }, 30000);
        return () => {
            active = false;
            window.clearTimeout(retryTimer);
            window.clearInterval(fallbackTimer);
            const socket = socketRef.current;
            if (socket?.readyState === WebSocket.OPEN)
                socket.close();
            else if (socket?.readyState === WebSocket.CONNECTING)
                socket.addEventListener('open', () => socket.close(), { once: true });
            socketRef.current = null;
        };
    }, [enabled, loadSnapshot]);

    return { analytics, loading, error, connection, lastUpdated };
}
