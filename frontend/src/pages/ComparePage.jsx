import { useEffect, useState } from 'react';
import { FiX } from 'react-icons/fi';
import { Link } from 'react-router-dom';
import { catalogApi } from '../api/services';
import { ProductPrice } from '../components/ProductPrice';
import { ProductRating } from '../components/ProductRating';
import { Alert, Button, EmptyState, Loader } from '../components/ui';
import { useCompare } from '../hooks/useCompare';
import { usePageMeta } from '../hooks/usePageMeta';
import { productPath } from '../utils/productPath';

export function ComparePage() {
    const { slugs, remove, clear } = useCompare();
    const [products, setProducts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    usePageMeta({ title: 'Compare products', description: 'Compare current prices, ratings, availability, and key product details at ECCO.' });

    useEffect(() => {
        if (!slugs.length) {
            setProducts([]);
            setLoading(false);
            return;
        }
        setLoading(true);
        Promise.allSettled(slugs.map((slug) => catalogApi.product(slug)))
            .then((results) => setProducts(results.filter((result) => result.status === 'fulfilled').map((result) => result.value)))
            .catch((reason) => setError(reason.message))
            .finally(() => setLoading(false));
    }, [slugs]);

    if (loading)
        return <div className="container page"><Loader label="Loading comparison"/></div>;
    return <div className="container page compare-page">
      <div className="page-heading"><div><p className="eyebrow">Choose confidently</p><h1>Compare products</h1><p>Review up to three products side by side.</p></div>{products.length > 0 && <Button variant="ghost" onClick={clear}>Clear comparison</Button>}</div>
      {error && <Alert>{error}</Alert>}
      {!products.length ? <EmptyState title="No products selected">Add products from the catalog to compare their current details.<br/><Link className="text-link" to="/products">Browse products</Link></EmptyState> : <div className="compare-table-wrap">
        <table className="compare-table">
          <thead><tr><th scope="col">Feature</th>{products.map((product) => <th scope="col" key={product.id}><button type="button" onClick={() => remove(product.slug)} aria-label={`Remove ${product.name} from comparison`}><FiX/></button><Link to={productPath(product)}>{product.image ? <img src={product.image} alt=""/> : <span>ECCO</span>}<strong>{product.name}</strong></Link></th>)}</tr></thead>
          <tbody>
            <tr><th scope="row">Price</th>{products.map((product) => <td key={product.id}><ProductPrice product={product}/></td>)}</tr>
            <tr><th scope="row">Category</th>{products.map((product) => <td key={product.id}>{product.category_name}</td>)}</tr>
            <tr><th scope="row">Customer rating</th>{products.map((product) => <td key={product.id}><ProductRating value={product.rating_average} count={product.review_count} compact/></td>)}</tr>
            <tr><th scope="row">Availability</th>{products.map((product) => <td key={product.id}><span className={`stock-label ${product.stock_quantity > 0 ? 'is-available' : 'is-unavailable'}`}>{product.stock_quantity > 0 ? `${product.stock_quantity} in stock` : 'Out of stock'}</span></td>)}</tr>
            <tr><th scope="row">Overview</th>{products.map((product) => <td className="compare-description" key={product.id}>{product.description}</td>)}</tr>
            <tr><th scope="row"><span className="sr-only">Actions</span></th>{products.map((product) => <td key={product.id}><Link className="button button--primary" to={productPath(product)}>View product</Link></td>)}</tr>
          </tbody>
        </table>
      </div>}
    </div>;
}
