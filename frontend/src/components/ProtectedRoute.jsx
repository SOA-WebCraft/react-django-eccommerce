import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Loader } from './ui';
export function ProtectedRoute() {
    const { isAuthenticated, loading } = useAuth();
    const location = useLocation();
    if (loading)
        return <div className="container page"><Loader label="Restoring your session"/></div>;
    return isAuthenticated ? (<Outlet />) : (<Navigate to="/login" replace state={{ from: location.pathname }}/>);
}
