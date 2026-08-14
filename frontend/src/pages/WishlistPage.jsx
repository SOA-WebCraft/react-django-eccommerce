import { useState } from 'react';
import { FiHeart } from 'react-icons/fi';
import { ApiError } from '../api/client';
import { ProductCard } from '../components/ProductCard';
import { EmptyState, Loader } from '../components/ui';
import { useCart } from '../hooks/useCart';
import { useToast } from '../hooks/useToast';
import { useWishlist } from '../hooks/useWishlist';

export function WishlistPage() {
    const { items, loading } = useWishlist();
    const { cart, add } = useCart();
    const { notify } = useToast();
    const [addingProductId, setAddingProductId] = useState(null);
    const addToCart = async (product) => {
        setAddingProductId(product.id);
        try {
            await add(product.id, 1);
            notify(`${product.name} added to your bag.`, 'success');
        }
        catch (reason) {
            if (!(reason instanceof ApiError))
                notify(reason instanceof Error ? reason.message : 'Unable to add product.', 'error');
        }
        finally {
            setAddingProductId(null);
        }
    };
    return <div className="container page wishlist-page">
      <div className="page-heading"><div><p className="eyebrow">Saved for later</p><h1>Your wishlist</h1><p>{items.length} saved {items.length === 1 ? 'product' : 'products'}</p></div></div>
      {loading ? <Loader label="Loading wishlist"/> : items.length ? <div className="product-grid product-grid--catalog">{items.map((item) => <ProductCard key={item.id} product={item.product_detail} onAddToCart={item.product_detail.is_active ? addToCart : undefined} adding={addingProductId === item.product} inCart={Boolean(cart?.items.some((cartItem) => cartItem.product === item.product))}/>)}</div> : <EmptyState icon={<FiHeart/>} title="Your wishlist is empty">Save products with the heart button and they will appear here.</EmptyState>}
    </div>;
}
