import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { catalogApi } from '../api/services';
import { ProductCard } from '../components/ProductCard';
import { Alert, Button, EmptyState, Field, Loader, Pagination } from '../components/ui';
import { useToast } from '../hooks/useToast';
import { useAuth } from '../hooks/useAuth';
import { useCart } from '../hooks/useCart';
import { usePageMeta } from '../hooks/usePageMeta';
export function ProductListPage() {
    const { notify } = useToast();
    const { isAuthenticated } = useAuth();
    const { cart, add } = useCart();
    const navigate = useNavigate();
    const location = useLocation();
    const [params, setParams] = useSearchParams();
    const [products, setProducts] = useState([]);
    const [categories, setCategories] = useState([]);
    const [count, setCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [addingProductId, setAddingProductId] = useState(null);
    const [search, setSearch] = useState(params.get('search') || '');
    const [minPrice, setMinPrice] = useState(params.get('min_price') || '');
    const [maxPrice, setMaxPrice] = useState(params.get('max_price') || '');
    const page = Number(params.get('page') || 1);
    const categoryLabel = categories.find((category) => category.slug === params.get('category'))?.name;
    const searchLabel = params.get('search');
    usePageMeta({
        title: searchLabel ? `Search results for ${searchLabel}` : categoryLabel || 'Shop all products',
        description: categoryLabel
            ? `Shop ECCO's selection of ${categoryLabel.toLowerCase()}, with secure checkout and live stock availability.`
            : 'Browse smartphones, laptops, tablets, smartwatches, and accessories available from ECCO.',
    });
    useEffect(() => {
        catalogApi.categories().then((data) => setCategories(data.results)).catch(() => undefined);
    }, []);
    useEffect(() => {
        setLoading(true);
        setError('');
        catalogApi.products({
            search: params.get('search') || undefined,
            category: params.get('category') || undefined,
            min_price: params.get('min_price') || undefined,
            max_price: params.get('max_price') || undefined,
            ordering: params.get('ordering') || undefined,
            page,
        })
            .then((data) => { setProducts(data.results); setCount(data.count); })
            .catch((reason) => setError(reason.message))
            .finally(() => setLoading(false));
    }, [params, page]);
    const update = (values) => {
        const next = new URLSearchParams(params);
        Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
        if (!('page' in values))
            next.delete('page');
        setParams(next);
    };
    const submitFilters = (event) => {
        event.preventDefault();
        if ((minPrice && Number(minPrice) < 0) || (maxPrice && Number(maxPrice) < 0)) {
            setError('Price filters must be zero or greater.');
            notify('Price filters must be zero or greater.', 'error');
            return;
        }
        update({ search: search.trim(), min_price: minPrice, max_price: maxPrice });
        setFiltersOpen(false);
    };
    const addToCart = async (product) => {
        if (!isAuthenticated) {
            navigate('/login', { state: { from: `${location.pathname}${location.search}` } });
            return;
        }
        setAddingProductId(product.id);
        try {
            await add(product.id, 1);
            notify(`${product.name} added to your bag.`, 'success');
        }
        catch (reason) {
            if (!(reason instanceof ApiError)) {
                notify(reason instanceof Error ? reason.message : 'Unable to add product.', 'error');
            }
        }
        finally {
            setAddingProductId(null);
        }
    };
    return (<div className="container page">
      <div className="page-heading catalog-page-heading page-visual-banner">
        <div><p className="eyebrow">The collection</p><h1>All products</h1><p>{count} thoughtfully selected products</p></div>
        <Button className="filter-toggle" variant="secondary" onClick={() => setFiltersOpen(true)}>Filters</Button>
      </div>
      <div className="catalog-layout">
        {filtersOpen && <button className="drawer-backdrop" aria-label="Close filters" onClick={() => setFiltersOpen(false)}/>}
        <aside className={`filters ${filtersOpen ? 'filters--open' : ''}`} aria-label="Product filters">
          <div className="filters__header"><h2>Filter & discover</h2><button onClick={() => setFiltersOpen(false)} aria-label="Close filters">×</button></div>
          <form onSubmit={submitFilters}>
            <Field label="Search" name="product-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Product name"/>
            <fieldset><legend>Category</legend>
              <label className="radio"><input type="radio" name="category" checked={!params.get('category')} onChange={() => update({ category: '' })}/>All categories</label>
              {categories.map((category) => <label className="radio" key={category.id}><input type="radio" name="category" checked={params.get('category') === category.slug} onChange={() => update({ category: category.slug })}/>{category.name}</label>)}
            </fieldset>
            <fieldset><legend>Price range</legend><div className="price-fields ">
              <Field label="Minimum" name="min-price" type="number" min="0" step="0.01" value={minPrice} onChange={(e) => setMinPrice(e.target.value)}/>
              <Field label="Maximum" name="max-price" type="number" min="0" step="0.01" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)}/>
            </div></fieldset>
            <Button type="submit">Apply filters</Button>
            <Button type="button" variant="ghost" onClick={() => { setSearch(''); setMinPrice(''); setMaxPrice(''); setParams({}); }}>Clear all</Button>
          </form>
        </aside>
        <section aria-live="polite">
          <div className="catalog-toolbar">
            <span>{loading ? 'Updating…' : `${count} results`}</span>
            <label>Sort by
              <select value={params.get('ordering') || 'name'} onChange={(e) => update({ ordering: e.target.value })}>
                <option value="name">Name: A–Z</option><option value="-name">Name: Z–A</option>
                <option value="price">Price: low to high</option><option value="-price">Price: high to low</option>
                <option value="-created_at">Newest first</option>
              </select>
            </label>
          </div>
          {error ? <Alert>{error}</Alert> : loading ? <Loader label="Loading products"/> : products.length ? (<><div className="product-grid product-grid--catalog">{products.map((product) => <ProductCard key={product.id} product={product} onAddToCart={addToCart} adding={addingProductId === product.id} inCart={Boolean(cart?.items.some((item) => item.product === product.id))}/>)}</div>
              <Pagination page={page} count={count} onPage={(nextPage) => update({ page: String(nextPage) })}/></>) : <EmptyState title="No products found">Try removing a filter or searching for another product.</EmptyState>}
        </section>
      </div>
    </div>);
}
