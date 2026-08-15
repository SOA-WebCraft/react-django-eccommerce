import { useEffect, useId, useRef, useState } from 'react';
import { FiSearch } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { catalogApi } from '../api/services';
import { formatPrice } from '../utils/format';
import { productPath } from '../utils/productPath';

export function SearchBox({ className = '', inputId, placeholder = 'Search the store', onNavigate }) {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [activeIndex, setActiveIndex] = useState(-1);
    const generatedId = useId();
    const listId = `${generatedId}-suggestions`;
    const rootRef = useRef(null);
    const navigate = useNavigate();

    useEffect(() => {
        const value = query.trim();
        if (value.length < 2) {
            setResults([]);
            setOpen(false);
            setLoading(false);
            return undefined;
        }
        let cancelled = false;
        const timer = window.setTimeout(() => {
            setLoading(true);
            catalogApi.products({ search: value })
                .then((data) => {
                    if (!cancelled) {
                        setResults(data.results.slice(0, 5));
                        setOpen(true);
                        setActiveIndex(-1);
                    }
                })
                .catch(() => {
                    if (!cancelled) {
                        setResults([]);
                        setOpen(true);
                    }
                })
                .finally(() => {
                    if (!cancelled)
                        setLoading(false);
                });
        }, 250);
        return () => {
            cancelled = true;
            window.clearTimeout(timer);
        };
    }, [query]);

    useEffect(() => {
        const close = (event) => {
            if (rootRef.current && !rootRef.current.contains(event.target))
                setOpen(false);
        };
        document.addEventListener('pointerdown', close);
        return () => document.removeEventListener('pointerdown', close);
    }, []);

    const goTo = (path) => {
        setOpen(false);
        onNavigate?.();
        navigate(path);
    };
    const submit = (event) => {
        event.preventDefault();
        const value = query.trim();
        goTo(value ? `/products?search=${encodeURIComponent(value)}` : '/products');
    };
    const onKeyDown = (event) => {
        if (!open || !results.length)
            return;
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActiveIndex((index) => Math.min(index + 1, results.length - 1));
        }
        else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActiveIndex((index) => Math.max(index - 1, -1));
        }
        else if (event.key === 'Enter' && activeIndex >= 0) {
            event.preventDefault();
            goTo(productPath(results[activeIndex]));
        }
        else if (event.key === 'Escape') {
            setOpen(false);
        }
    };

    return <div className={`predictive-search ${className}`} ref={rootRef}>
      <form className="header-search" role="search" onSubmit={submit}>
        <label className="sr-only" htmlFor={inputId}>Search products</label>
        <input id={inputId} value={query} onChange={(event) => setQuery(event.target.value)} onFocus={() => query.trim().length >= 2 && setOpen(true)} onKeyDown={onKeyDown} placeholder={placeholder} role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls={listId} aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}/>
        <button type="submit" aria-label="Search"><FiSearch aria-hidden="true"/></button>
      </form>
      {open && <div className="search-suggestions" id={listId} role="listbox" aria-label="Product suggestions">
        {loading ? <p className="search-suggestions__message">Searching products…</p> : results.length ? <>
          {results.map((product, index) => <button id={`${listId}-${index}`} type="button" role="option" aria-selected={activeIndex === index} className={activeIndex === index ? 'is-active' : ''} key={product.id} onMouseEnter={() => setActiveIndex(index)} onClick={() => goTo(productPath(product))}>
            <span className="search-suggestions__image">{product.image ? <img src={product.image} alt=""/> : 'E'}</span>
            <span><strong>{product.name}</strong><small>{product.category_name}</small></span>
            <b>{formatPrice(product.effective_price || product.price)}</b>
          </button>)}
          <button type="button" className="search-suggestions__all" onClick={() => goTo(`/products?search=${encodeURIComponent(query.trim())}`)}>View all results for “{query.trim()}”</button>
        </> : <p className="search-suggestions__message">No products found. Try a broader search.</p>}
      </div>}
    </div>;
}
