import { formatPrice } from '../utils/format';

export function ProductPrice({ product, detail = false }) {
    const hasPromotion = product.promotional_price !== null
        && product.promotional_price !== undefined;
    return (<div className={`product-price${detail ? ' product-price--detail' : ''}`}>
      {hasPromotion && <del className="product-price__original">{formatPrice(product.price)}</del>}
      <strong className="product-price__current">
        {formatPrice(hasPromotion ? product.promotional_price : product.price)}
      </strong>
      {hasPromotion && <span className="product-price__badge">-{Number(product.promotion_percentage)}%</span>}
    </div>);
}
