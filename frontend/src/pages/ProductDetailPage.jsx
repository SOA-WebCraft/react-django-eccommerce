import { useEffect, useState } from 'react';
import { FiShoppingCart } from 'react-icons/fi';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { catalogApi } from '../api/services';
import { ApiError } from '../api/client';
import { ProductCard } from '../components/ProductCard';
import { Alert, Button, Loader, QuantityControl } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { useCart } from '../hooks/useCart';
import { useToast } from '../hooks/useToast';
import { formatPrice } from '../utils/format';
import { productPath } from '../utils/productPath';
export function ProductDetailPage() {
    const { slug = '' } = useParams();
    const navigate = useNavigate();
    const { isAuthenticated } = useAuth();
    const { cart, add, adjust } = useCart();
    const { notify } = useToast();
    const [product, setProduct] = useState(null);
    const [related, setRelated] = useState([]);
    const [selectedImage, setSelectedImage] = useState('');
    const [loading, setLoading] = useState(true);
    const [adding, setAdding] = useState(false);
    const [error, setError] = useState('');
    useEffect(() => {
        setLoading(true);
        catalogApi.product(slug)
            .then(async (data) => {
            setProduct(data);
            setSelectedImage(data.image || data.gallery_images[0]?.image || '');
            const result = await catalogApi.products({ category: data.category_name.toLowerCase().replaceAll(' ', '-') });
            setRelated(result.results.filter((item) => item.id !== data.id).slice(0, 4));
        })
            .catch((reason) => setError(reason.message))
            .finally(() => setLoading(false));
    }, [slug]);
    const cartItem = product
        ? cart?.items.find((item) => item.product === product.id)
        : undefined;
    if (loading)
        return <div className="container page"><Loader label="Loading product"/></div>;
    if (error || !product)
        return <div className="container page"><Alert>{error || 'Product not found.'}</Alert><Link to="/products">Return to products</Link></div>;
    const images = [product.image, ...product.gallery_images.map((item) => item.image)].filter(Boolean);
    const sections = product.description.split(/\n\n+/);
    const addToCart = async () => {
        if (!isAuthenticated) {
            navigate('/login', { state: { from: productPath(product) } });
            return;
        }
        setAdding(true);
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
            setAdding(false);
        }
    };
    const changeQuantity = async (operation) => {
        setAdding(true);
        try {
            await adjust(cartItem.id, operation);
        }
        catch (reason) {
            if (!(reason instanceof ApiError)) {
                notify(reason instanceof Error ? reason.message : 'Unable to update cart quantity.', 'error');
            }
        }
        finally {
            setAdding(false);
        }
    };
    return (<div className="container page">
      <nav className="breadcrumbs" aria-label="Breadcrumb"><Link to="/">Home</Link><span>/</span><Link to="/products">Products</Link><span>/</span><span>{product.name}</span></nav>
      <article className="product-detail">
        <div className="gallery">
          <div className="gallery__main">{selectedImage ? <img src={selectedImage} alt={product.name}/> : <span>ECCO</span>}</div>
          {images.length > 1 && <div className="gallery__thumbs">{images.map((image, index) => <button key={image} className={selectedImage === image ? 'is-active' : ''} onClick={() => setSelectedImage(image)} aria-label={`View image ${index + 1}`}><img src={image} alt=""/></button>)}</div>}
        </div>
        <div className="product-info">
          <p className="eyebrow">{product.category_name}</p><h1>{product.name}</h1>
          <p className="product-info__price">{formatPrice(product.price)}</p>
          <div className={`stock ${product.stock_quantity ? 'stock--in' : 'stock--out'}`}><span />{product.stock_quantity ? `${product.stock_quantity} in stock` : 'Out of stock'}</div>
          <div className="description">{sections.map((section, index) => {
            const [heading, ...body] = section.split('\n');
            return body.length ? <section key={heading}><h2>{heading}</h2><p>{body.join(' ')}</p></section> : <p key={index}>{heading}</p>;
        })}</div>
          <div className="purchase-panel">
            {cartItem && <QuantityControl value={cartItem.quantity} max={Math.max(1, product.stock_quantity)} onDecrease={() => void changeQuantity('decrement')} onIncrease={() => void changeQuantity('increment')} disabled={!product.stock_quantity || adding}/>}
            {!cartItem && <Button className="add-to-cart-button" onClick={addToCart} disabled={!product.stock_quantity || adding}>{!adding && <FiShoppingCart aria-hidden="true"/>}{adding ? 'Adding…' : 'Add to cart'}</Button>}
          </div>
          <p className="purchase-note">Inventory and total are validated securely when your order is placed.</p>
        </div>
      </article>
      {related.length > 0 && <section className="section"><div className="section-heading"><div><p className="eyebrow">Keep exploring</p><h2>Related products</h2></div></div><div className="product-grid product-grid--four">{related.map((item) => <ProductCard key={item.id} product={item}/>)}</div></section>}
    </div>);
}
