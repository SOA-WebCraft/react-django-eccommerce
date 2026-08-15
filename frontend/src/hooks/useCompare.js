import { useContext } from 'react';
import { CompareContext } from '../components/CompareContext';

export function useCompare() {
    const value = useContext(CompareContext);
    if (!value)
        throw new Error('useCompare must be used within CompareProvider.');
    return value;
}
