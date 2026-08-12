import { useEffect, useMemo, useState } from 'react';
import { onUnauthorized } from '../api/client';
import { authApi } from '../api/services';
import { AuthContext } from './AuthContext';
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        onUnauthorized(() => setUser(null));
        const restoreSession = async () => {
            try {
                await authApi.csrf();
                setUser(await authApi.me(false));
            }
            catch {
                setUser(null);
            }
            finally {
                setLoading(false);
            }
        };
        void restoreSession();
        return () => onUnauthorized(null);
    }, []);
    const value = useMemo(() => ({
        user,
        loading,
        isAuthenticated: Boolean(user),
        async login(username, password) {
            const authenticatedUser = await authApi.login(username, password);
            setUser(authenticatedUser);
            return authenticatedUser;
        },
        async logout() {
            try {
                await authApi.logout();
            }
            finally {
                setUser(null);
            }
        },
        async updateProfile(profile) {
            const updated = await authApi.updateProfile(profile);
            setUser(updated);
            return updated;
        },
    }), [user, loading]);
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
