import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { checkoutApi, orderApi } from '../api/services';
import { ApiError } from '../api/client';
import { Alert, Button, EmptyState, Field, Loader } from '../components/ui';
import { useCart } from '../hooks/useCart';
import { useToast } from '../hooks/useToast';
import { useAuth } from '../hooks/useAuth';
import { formatPrice } from '../utils/format';
import { OrderDetailContent } from './OrderPages';

export function CheckoutPage() {
    const { user } = useAuth();
    const { cart, loading } = useCart();
    const { notify } = useToast();
    const [submitting, setSubmitting] = useState(false);
    const [quoting, setQuoting] = useState(true);
    const [quote, setQuote] = useState(null);
    const [couponCode, setCouponCode] = useState('');
    const [appliedCoupon, setAppliedCoupon] = useState('');
    const [giftCardCode, setGiftCardCode] = useState('');
    const [appliedGiftCard, setAppliedGiftCard] = useState('');
    const [searchParams] = useSearchParams();
    const [error, setError] = useState('');
    const [errors, setErrors] = useState({});
    const [methods, setMethods] = useState([]);
    const [paymentChoice, setPaymentChoice] = useState('');
    const [form, setForm] = useState({
        name: [user?.first_name, user?.last_name].filter(Boolean).join(' '),
        email: user?.email || '',
        address: user?.address || '',
        city: user?.city || '',
        postal: user?.postal_code || '',
        country: user?.country || '',
    });
    useEffect(() => {
        if (searchParams.get('cancelled') === '1')
            setError('Stripe Checkout was cancelled. Your cart was not changed.');
        checkoutApi.quote()
            .then(setQuote)
            .catch((reason) => setError(reason.message))
            .finally(() => setQuoting(false));
        checkoutApi.methods().then((data) => {
            setMethods(data.results);
            if (data.results.length)
                setPaymentChoice(`${data.results[0].provider}:${data.results[0].method}`);
        }).catch((reason) => setError(reason.message));
    }, [searchParams]);
    if (loading && !cart)
        return <div className="container page"><Loader /></div>;
    if (!cart?.items.length)
        return <div className="container page"><EmptyState title="Your bag is empty" action={<Link className="button button--primary" to="/products">Shop products</Link>}>Add an item before starting checkout.</EmptyState></div>;
    const applyCoupon = async () => {
        setQuoting(true);
        setError('');
        try {
            const normalizedCode = couponCode.trim();
            setQuote(await checkoutApi.quote(normalizedCode, appliedGiftCard));
            setAppliedCoupon(normalizedCode);
            notify(
                couponCode.trim() ? 'Coupon applied.' : 'Coupon removed.',
                'success',
            );
        }
        catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Invalid coupon.');
        }
        finally {
            setQuoting(false);
        }
    };
    const applyGiftCard = async () => {
        setQuoting(true); setError('');
        try {
            const normalized = giftCardCode.trim();
            setQuote(await checkoutApi.quote(appliedCoupon, normalized));
            setAppliedGiftCard(normalized);
            notify(normalized ? 'Gift card applied.' : 'Gift card removed.', 'success');
        } catch (reason) { setError(reason.message); }
        finally { setQuoting(false); }
    };
    const submit = async (event) => {
        event.preventDefault();
        const nextErrors = {};
        Object.entries(form).forEach(([key, value]) => {
            if (!value.trim())
                nextErrors[key] = 'This field is required.';
        });
        if (form.email && !form.email.includes('@'))
            nextErrors.email = 'Enter a valid email address.';
        if (Object.keys(nextErrors).length) {
            setErrors(nextErrors);
            return;
        }
        setErrors({});
        setError('');
        setSubmitting(true);
        try {
            const [provider, method] = paymentChoice.split(':');
            const checkout = await checkoutApi.createPayment({
                provider,
                method,
                billing_name: form.name.trim(),
                billing_email: form.email.trim(),
                address: form.address.trim(),
                city: form.city.trim(),
                postal_code: form.postal.trim(),
                country: form.country.trim(),
                coupon_code: appliedCoupon,
                gift_card_code: appliedGiftCard,
            });
            window.location.assign(checkout.checkout_url);
        }
        catch (reason) {
            const message = reason instanceof Error
                ? reason.message
                : 'Unable to start payment.';
            setError(message);
            if (!(reason instanceof ApiError))
                notify(message, 'error');
            setSubmitting(false);
        }
    };
    const input = (name, label, options = {}) => <Field label={label} name={name} value={form[name]} error={errors[name]} onChange={(event) => setForm({ ...form, [name]: event.target.value })} {...options}/>;
    return <div className="container page"><div className="page-heading"><div><p className="eyebrow">Secure checkout</p><h1>Delivery and payment</h1></div></div>
      <div className="checkout-layout"><form className="checkout-form" onSubmit={submit}>
        {error && <Alert>{error}</Alert>}
        <div className="form-grid">{input('name', 'Full name', { autoComplete: 'name' })}{input('email', 'Email address', { type: 'email', autoComplete: 'email' })}<div className="field--wide">{input('address', 'Street address', { autoComplete: 'street-address' })}</div>{input('city', 'City', { autoComplete: 'address-level2' })}{input('postal', 'Postal code', { autoComplete: 'postal-code' })}<div className="field--wide">{input('country', 'Country', { autoComplete: 'country-name' })}</div></div>
        <div className="coupon-field"><Field label="Coupon code" name="coupon" value={couponCode} onChange={(event) => setCouponCode(event.target.value)}/><Button type="button" variant="secondary" disabled={quoting} onClick={() => void applyCoupon()}>{quoting ? 'Checking…' : 'Apply coupon'}</Button></div>
        <div className="coupon-field"><Field label="Gift card" name="gift-card" value={giftCardCode} onChange={(event) => setGiftCardCode(event.target.value)}/><Button type="button" variant="secondary" disabled={quoting} onClick={() => void applyGiftCard()}>{quoting ? 'Checking…' : 'Apply gift card'}</Button></div>
        <fieldset className="payment-choice"><legend>Payment method</legend>{methods.map((item) => <label key={`${item.provider}:${item.method}`}><input type="radio" name="payment_method" value={`${item.provider}:${item.method}`} checked={paymentChoice === `${item.provider}:${item.method}`} onChange={(event) => setPaymentChoice(event.target.value)}/><span><strong>{item.label}</strong><small>{item.description}</small></span></label>)}</fieldset>
        <Button type="submit" disabled={submitting || quoting || !quote || !paymentChoice}>{submitting ? 'Opening secure payment…' : 'Continue to secure payment'}</Button>
      </form>
      <aside className="order-summary"><h2>Your order</h2>{cart.items.map((item) => <div key={item.id}><span>{item.product_detail.name} × {item.quantity}</span><strong>{formatPrice(item.line_total)}</strong></div>)}<hr />{quote ? <><div><span>Subtotal</span><strong>{formatPrice(quote.subtotal, quote.currency)}</strong></div>{Number(quote.promotion_discount) > 0 && <div><span>Promotions</span><strong>-{formatPrice(quote.promotion_discount, quote.currency)}</strong></div>}{Number(quote.coupon_discount) > 0 && <div><span>Coupon</span><strong>-{formatPrice(quote.coupon_discount, quote.currency)}</strong></div>}<div><span>Shipping</span><strong>{formatPrice(quote.shipping, quote.currency)}</strong></div><div><span>Tax</span><strong>{formatPrice(quote.tax, quote.currency)}</strong></div>{Number(quote.gift_card_discount) > 0 && <div><span>Gift card</span><strong>-{formatPrice(quote.gift_card_discount, quote.currency)}</strong></div>}<div className="order-summary__total"><span>Total</span><strong>{formatPrice(quote.total, quote.currency)}</strong></div></> : <Loader label="Calculating total"/>}<p>Payment is completed on the selected provider's secure hosted page.</p></aside></div>
    </div>;
}

export function ConfirmationPage() {
    const { orderId: checkoutId = '' } = useParams();
    const { refresh } = useCart();
    const [attempt, setAttempt] = useState(null);
    const [order, setOrder] = useState(null);
    const [error, setError] = useState('');
    useEffect(() => {
        let cancelled = false;
        let timer;
        const poll = async () => {
            try {
                const status = await checkoutApi.status(checkoutId);
                if (cancelled)
                    return;
                setAttempt(status);
                if (status.status === 'fulfilled' && status.order_id) {
                    setOrder(await orderApi.detail(status.order_id));
                    await refresh();
                    return;
                }
                if (['refunded', 'refund_failed', 'failed', 'expired'].includes(status.status))
                    return;
                timer = window.setTimeout(poll, 1500);
            }
            catch (reason) {
                if (!cancelled)
                    setError(reason instanceof Error ? reason.message : 'Unable to verify payment.');
            }
        };
        void poll();
        return () => {
            cancelled = true;
            if (timer)
                window.clearTimeout(timer);
        };
    }, [checkoutId, refresh]);
    if (error)
        return <div className="container page"><Alert>{error}</Alert></div>;
    if (!attempt || !['fulfilled', 'refunded', 'refund_failed', 'failed', 'expired'].includes(attempt.status))
        return <div className="container page"><Loader label="Confirming payment and preparing your invoice"/></div>;
    if (attempt.status !== 'fulfilled')
        return <div className="container page"><Alert>{attempt.error_message || `Checkout status: ${attempt.status}`}</Alert><Link to="/cart">Return to cart</Link></div>;
    return <div className="container page confirmation"><div className="confirmation__mark" aria-hidden="true">✓</div><p className="eyebrow">Payment confirmed</p><h1>Thank you for your order.</h1><p>Your order and invoice have been created securely.</p>{order && <OrderDetailContent order={order}/>}<div className="confirmation__actions"><Link className="button button--primary" to="/account/orders">View all orders</Link><Link className="button button--secondary" to="/products">Continue shopping</Link></div></div>;
}
