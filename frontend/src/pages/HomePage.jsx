import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { catalogApi } from '../api/services';
import { ProductCard } from '../components/ProductCard';
import { Alert, Loader } from '../components/ui';
const categorySymbols = {
    smartphones: '▯',
    laptops: '▱',
    tablets: '▭',
    smartwatches: '◫',
    accessories: '⌁',
};
export function HomePage() {
    const [featured, setFeatured] = useState([]);
    const [newArrivals, setNewArrivals] = useState([]);
    const [categories, setCategories] = useState([]);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        Promise.all([
            catalogApi.products(),
            catalogApi.products({ ordering: '-created_at' }),
            catalogApi.categories(),
        ])
            .then(([products, newest, categoryData]) => {
            setFeatured(products.results.slice(0, 8));
            setNewArrivals(newest.results.slice(0, 4));
            setCategories(categoryData.results);
        })
            .catch((reason) => setError(reason.message))
            .finally(() => setLoading(false));
    }, []);
    return (<>
      <section className="hero">
        <div className="container hero__content">
          <p className="eyebrow">The new standard in personal tech</p>
          <h1>Remarkable technology.<br />Selected with purpose.</h1>
          <p>Explore flagship devices and everyday essentials designed to move at your pace.</p>
          <div className="hero__actions">
            <Link className="button button--primary" to="/products">Shop the collection</Link>
            <Link className="button button--glass" to="/products?ordering=-created_at">Discover what’s new</Link>
          </div>
        </div>
        <div className="hero__orb hero__orb--one"/><div className="hero__orb hero__orb--two"/>
      </section>

      <section className="section container">
        <div className="section-heading"><div><p className="eyebrow">Find your fit</p><h2>Shop by category</h2></div></div>
        {loading ? <Loader label="Loading categories"/> : error ? <Alert>{error}</Alert> : (<div className="category-grid">
            {categories.map((category) => (<Link className="category-tile" key={category.id} to={`/products?category=${category.slug}`}>
                <span aria-hidden="true">{categorySymbols[category.slug] || '◇'}</span>
                <strong>{category.name}</strong>
                <small>Explore collection →</small>
              </Link>))}
          </div>)}
      </section>

      <section className="section section--tint">
        <div className="container">
          <div className="section-heading">
            <div><p className="eyebrow">Editor’s selection</p><h2>Featured technology</h2></div>
            <Link className="text-link" to="/products">View all products</Link>
          </div>
          {loading ? <Loader label="Loading products"/> : error ? <Alert>{error}</Alert> : (<div className="product-grid">{featured.map((product) => <ProductCard key={product.id} product={product}/>)}</div>)}
        </div>
      </section>

      <section className="promo-band container">
        <div><p className="eyebrow">Built for more</p><h2>Power your best ideas.</h2><p>Discover high-performance laptops and tablets for ambitious work, wherever it happens.</p><Link className="button button--secondary" to="/products?category=laptops">Shop laptops</Link></div>
        <div className="promo-art" aria-hidden="true"><span>01</span><span>10</span><span>11</span></div>
      </section>

      <section className="section container">
        <div className="section-heading">
          <div><p className="eyebrow">Just landed</p><h2>New arrivals</h2></div>
          <Link className="text-link" to="/products?ordering=-created_at">See what’s new</Link>
        </div>
        {loading ? <Loader /> : <div className="product-grid product-grid--four">{newArrivals.map((product) => <ProductCard key={product.id} product={product}/>)}</div>}
      </section>

      <section className="benefits">
        <div className="container benefits__grid">
          <div><strong>Secure account</strong><span>Session-protected shopping and orders</span></div>
          <div><strong>Live inventory</strong><span>Stock checked when you order</span></div>
          <div><strong>Clear history</strong><span>Every order saved to your profile</span></div>
        </div>
      </section>
    </>);
}
