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
            setAnalytics(data);
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
                    retryCount = 0;
                    setConnection('live');
                    setError('');
                });
                socket.addEventListener('message', (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        if (message.type !== 'analytics.snapshot')
                            return;
                        setAnalytics(message.data);
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
                socket.addEventListener('error', () => socket.close());
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
            socketRef.current?.close();
            socketRef.current = null;
        };
    }, [enabled, loadSnapshot]);

    return { analytics, loading, error, connection, lastUpdated };
}
