import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FiHeart, FiShoppingCart } from 'react-icons/fi';
import { ApiError } from '../api/client';
import { Button } from './ui';
import { ProductRating } from './ProductRating';
import { ProductPrice } from './ProductPrice';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { useWishlist } from '../hooks/useWishlist';
import { productPath } from '../utils/productPath';
export function ProductCard({ product, onAddToCart, adding = false, inCart = false }) {
    const detailPath = productPath(product);
    const { isAuthenticated } = useAuth();
    const { has, toggle } = useWishlist();
    const { notify } = useToast();
    const navigate = useNavigate();
    const location = useLocation();
    const [savingWishlist, setSavingWishlist] = useState(false);
    const wishlisted = has(product.id);
    const available = product.is_active && product.stock_quantity > 0;
    const toggleWishlist = async () => {
        if (!isAuthenticated) {
            navigate('/login', { state: { from: `${location.pathname}${location.search}` } });
            return;
        }
        setSavingWishlist(true);
        try {
            const added = await toggle(product.id);
            notify(added ? `${product.name} saved to your wishlist.` : `${product.name} removed from your wishlist.`, 'success');
        }
        catch (reason) {
            if (!(reason instanceof ApiError))
                notify(reason instanceof Error ? reason.message : 'Unable to update your wishlist.', 'error');
        }
        finally {
            setSavingWishlist(false);
        }
    };
    return (<article className="product-card">
      <Link to={detailPath} className="product-card__image">
        {product.image ? (<img src={product.image} alt={product.name} loading="lazy"/>) : (<span aria-hidden="true">ECCO</span>)}
        {!available && <span className="badge">{product.is_active ? 'Sold out' : 'Unavailable'}</span>}
      </Link>
      <button type="button" className={`product-card__wishlist${wishlisted ? ' is-saved' : ''}`} onClick={() => void toggleWishlist()} disabled={savingWishlist} aria-label={wishlisted ? `Remove ${product.name} from wishlist` : `Save ${product.name} to wishlist`} aria-pressed={wishlisted}><FiHeart aria-hidden="true"/></button>
      <div className="product-card__body">
        <p className="eyebrow">{product.category_name}</p>
        <h3><Link to={detailPath}>{product.name}</Link></h3>
        <ProductRating value={product.rating_average} count={product.review_count} compact/>
        <div className="product-card__footer">
          <ProductPrice product={product}/>
          {onAddToCart ? (<Button
            className="product-card__cart-button"
            onClick={() => onAddToCart(product)}
            disabled={!available || adding || inCart}
            aria-label={!available ? `${product.name} is unavailable` : inCart ? `${product.name} is already in your cart` : `Add ${product.name} to cart`}
          >
            {!adding && <FiShoppingCart aria-hidden="true"/>}
            {adding ? 'Adding…' : !available ? 'Unavailable' : inCart ? 'Added' : 'Add'}
          </Button>) : (<Link className="text-link" to={detailPath} aria-label={`View ${product.name}`}>
              View
            </Link>)}
        </div>
      </div>
    </article>);
}
