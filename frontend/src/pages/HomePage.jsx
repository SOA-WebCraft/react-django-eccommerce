import { useEffect, useState } from 'react';
import { FiArrowRight, FiChevronLeft, FiChevronRight } from 'react-icons/fi';
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
const categoryBanners = [
    { slug: 'accessories', title: 'Accessories that complete the setup.', copy: 'Power, sound, storage and everyday essentials selected to work beautifully together.', image: '/images/category-accessories.webp' },
    { slug: 'laptops', title: 'Performance made portable.', copy: 'Explore capable laptops for focused work, ambitious ideas and everything between.', image: '/images/category-laptops.webp' },
    { slug: 'smartphones', title: 'Your world, always within reach.', copy: 'Discover flagship smartphones built for exceptional photos, speed and connection.', image: '/images/category-smartphones.webp' },
    { slug: 'smartwatches', title: 'Move smarter every day.', copy: 'Keep time, health and daily goals close with modern watches designed for real life.', image: '/images/category-smartwatches.webp' },
    { slug: 'tablets', title: 'Create, watch and work anywhere.', copy: 'Find versatile tablets that shift effortlessly from entertainment to productivity.', image: '/images/category-tablets.webp' },
];
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

      <CategoryBannerCarousel />

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

function CategoryBannerCarousel() {
    const [active, setActive] = useState(0);
    const [paused, setPaused] = useState(false);
    useEffect(() => {
        if (paused || window.matchMedia('(prefers-reduced-motion: reduce)').matches)
            return undefined;
        const timer = window.setInterval(
            () => setActive((current) => (current + 1) % categoryBanners.length),
            6000,
        );
        return () => window.clearInterval(timer);
    }, [paused]);
    const move = (direction) => {
        setActive((current) => (current + direction + categoryBanners.length) % categoryBanners.length);
    };
    return (<section
      className="category-showcase container"
      aria-label="Shop featured categories"
      aria-roledescription="carousel"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
            setPaused(false);
    }}
    >
      <div className="category-showcase__viewport" aria-live="polite">
        {categoryBanners.map((banner, index) => <article
          className={`category-showcase__slide${index === active ? ' is-active' : ''}`}
          style={{ backgroundImage: `linear-gradient(90deg, rgba(3, 18, 14, .98), rgba(5, 45, 32, .84) 43%, rgba(5, 45, 32, .08) 76%), url(${banner.image})` }}
          aria-hidden={index !== active}
          key={banner.slug}
        >
          <div className="category-showcase__content">
            <p className="eyebrow">Explore {banner.slug}</p>
            <h2>{banner.title}</h2>
            <p>{banner.copy}</p>
            <Link className="button button--secondary" to={`/products?category=${banner.slug}`} tabIndex={index === active ? 0 : -1}>
              Shop {banner.slug} <FiArrowRight aria-hidden="true"/>
            </Link>
          </div>
        </article>)}
      </div>
      <button className="category-showcase__arrow category-showcase__arrow--previous" type="button" onClick={() => move(-1)} aria-label="Previous category"><FiChevronLeft aria-hidden="true"/></button>
      <button className="category-showcase__arrow category-showcase__arrow--next" type="button" onClick={() => move(1)} aria-label="Next category"><FiChevronRight aria-hidden="true"/></button>
      <div className="category-showcase__controls" role="group" aria-label="Choose category banner">
        {categoryBanners.map((banner, index) => <button type="button" className={index === active ? 'is-active' : ''} onClick={() => setActive(index)} aria-label={`Show ${banner.slug}`} aria-current={index === active ? 'true' : undefined} key={banner.slug}><span /></button>)}
      </div>
    </section>);
}
