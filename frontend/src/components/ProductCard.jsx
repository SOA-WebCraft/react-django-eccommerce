import { Link } from 'react-router-dom';
import { FiShoppingCart } from 'react-icons/fi';
import { Button } from './ui';
import { formatPrice } from '../utils/format';
import { productPath } from '../utils/productPath';
export function ProductCard({ product, onAddToCart, adding = false, inCart = false }) {
    const detailPath = productPath(product);
    return (<article className="product-card">
      <Link to={detailPath} className="product-card__image">
        {product.image ? (<img src={product.image} alt={product.name} loading="lazy"/>) : (<span aria-hidden="true">ECCO</span>)}
        {product.stock_quantity === 0 && <span className="badge">Sold out</span>}
      </Link>
      <div className="product-card__body">
        <p className="eyebrow">{product.category_name}</p>
        <h3><Link to={detailPath}>{product.name}</Link></h3>
        <div className="product-card__footer">
          <strong>{formatPrice(product.price)}</strong>
          {onAddToCart ? (<Button
            className="product-card__cart-button"
            onClick={() => onAddToCart(product)}
            disabled={product.stock_quantity === 0 || adding || inCart}
            aria-label={product.stock_quantity === 0 ? `${product.name} is sold out` : inCart ? `${product.name} is already in your cart` : `Add ${product.name} to cart`}
          >
            {!adding && <FiShoppingCart aria-hidden="true"/>}
            {adding ? 'Adding…' : product.stock_quantity === 0 ? 'Sold out' : inCart ? 'Added' : 'Add'}
          </Button>) : (<Link className="text-link" to={detailPath} aria-label={`View ${product.name}`}>
              View
            </Link>)}
        </div>
      </div>
    </article>);
}
