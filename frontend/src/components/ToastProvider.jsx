import { useCallback, useMemo } from 'react';
import { toast, ToastContainer } from 'react-toastify';
import { ToastContext } from './ToastContext';
export function ToastProvider({ children }) {
    const notify = useCallback((message, kind = 'info') => {
        toast[kind](message);
    }, []);
    const value = useMemo(() => ({ notify }), [notify]);
    return (<ToastContext.Provider value={value}>
      {children}
      <ToastContainer position="top-right" autoClose={4000} newestOnTop/>
    </ToastContext.Provider>);
}
