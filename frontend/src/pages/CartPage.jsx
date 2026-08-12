import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError } from '../api/client';
import { Alert, EmptyState, Loader, QuantityControl } from '../components/ui';
import { useCart } from '../hooks/useCart';
import { useToast } from '../hooks/useToast';
import { formatPrice } from '../utils/format';
import { productPath } from '../utils/productPath';
export function CartPage() {
    const { cart, loading, adjust, remove } = useCart();
    const { notify } = useToast();
    const [busy, setBusy] = useState(null);
    const [error, setError] = useState('');
    const [pendingRemoval, setPendingRemoval] = useState(null);
    const mutate = async (id, action, success) => {
        setBusy(id);
        setError('');
        try {
            await action();
            notify(success, 'success');
            return true;
        }
        catch (reason) {
            const message = reason instanceof Error ? reason.message : 'Unable to update your bag.';
            setError(message);
            if (!(reason instanceof ApiError))
                notify(message, 'error');
            return false;
        }
        finally {
            setBusy(null);
        }
    };
    if (loading && !cart)
        return <div className="container page"><Loader label="Loading your bag"/></div>;
    if (!cart?.items.length)
        return <div className="container page"><EmptyState title="Your bag is ready for something brilliant" action={<Link className="button button--primary" to="/products">Explore products</Link>}>Products you add will be saved to your account cart.</EmptyState></div>;
    return (<div className="container page">
      <div className="page-heading"><div><p className="eyebrow">Your selection</p><h1>Shopping bag</h1><p>{cart.items.length} unique {cart.items.length === 1 ? 'item' : 'items'}</p></div></div>
      {error && <Alert>{error}</Alert>}
      <div className="cart-layout">
        <section className="cart-items" aria-label="Cart items">
          {cart.items.map((item) => {
            const unavailable = !item.product_detail.is_active || item.product_detail.stock_quantity === 0;
            const detailPath = productPath(item.product_detail);
            return <article className="cart-item" key={item.id}>
              <Link to={detailPath} className="cart-item__image">{item.product_detail.image ? <img src={item.product_detail.image} alt={item.product_detail.name}/> : <span>ECCO</span>}</Link>
              <div className="cart-item__info"><p className="eyebrow">{item.product_detail.category_name}</p><h2><Link to={detailPath}>{item.product_detail.name}</Link></h2><p>{formatPrice(item.product_detail.price)}</p>
                {unavailable && <span className="item-warning">Currently unavailable</span>}
                <div className="cart-item__actions">
                  <QuantityControl value={item.quantity} max={Math.max(1, item.product_detail.stock_quantity)} disabled={busy === item.id || unavailable} onDecrease={() => void mutate(item.id, () => adjust(item.id, 'decrement'), 'Quantity updated.')} onIncrease={() => void mutate(item.id, () => adjust(item.id, 'increment'), 'Quantity updated.')}/>
                  <button className="text-button" disabled={busy === item.id} onClick={() => setPendingRemoval(item)}>Remove</button>
                </div>
              </div>
              <div className="cart-item__subtotal">
                <span>Subtotal</span>
                <strong>{formatPrice(item.line_total)}</strong>
              </div>
            </article>;
        })}
        </section>
        <aside className="order-summary"><h2>Order summary</h2><div><span>Subtotal</span><strong>{formatPrice(cart.total)}</strong></div><div><span>Delivery</span><strong>Calculated later</strong></div><hr /><div className="order-summary__total"><span>Total</span><strong>{formatPrice(cart.total)}</strong></div>
          <Link className={`button button--primary button--wide ${cart.items.some((item) => !item.product_detail.is_active || !item.product_detail.stock_quantity) ? 'is-disabled' : ''}`} to="/checkout">Continue to checkout</Link>
          <p>Stock and pricing are confirmed when the order is placed.</p>
        </aside>
      </div>
      {pendingRemoval && <RemoveCartItemModal item={pendingRemoval} deleting={busy === pendingRemoval.id} onCancel={() => setPendingRemoval(null)} onConfirm={async () => {
        const removed = await mutate(pendingRemoval.id, () => remove(pendingRemoval.id), 'Item removed.');
        if (removed)
            setPendingRemoval(null);
    }}/>}
    </div>);
}

function RemoveCartItemModal({ item, deleting, onCancel, onConfirm }) {
    const cancelButton = useRef(null);
    useEffect(() => {
        cancelButton.current?.focus();
        const closeOnEscape = (event) => {
            if (event.key === 'Escape' && !deleting)
                onCancel();
        };
        document.addEventListener('keydown', closeOnEscape);
        return () => document.removeEventListener('keydown', closeOnEscape);
    }, [deleting, onCancel]);
    return (<div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
        if (event.target === event.currentTarget && !deleting)
            onCancel();
    }}>
      <section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="remove-item-title" aria-describedby="remove-item-description">
        <p className="eyebrow">Confirm removal</p>
        <h2 id="remove-item-title">Remove this item?</h2>
        <p id="remove-item-description">{item.product_detail.name} will be removed from your shopping bag.</p>
        <div className="confirm-modal__actions">
          <button ref={cancelButton} className="button button--secondary" type="button" disabled={deleting} onClick={onCancel}>Cancel</button>
          <button className="button button--danger" type="button" disabled={deleting} onClick={() => void onConfirm()}>{deleting ? 'Removing…' : 'Remove item'}</button>
        </div>
      </section>
    </div>);
}
