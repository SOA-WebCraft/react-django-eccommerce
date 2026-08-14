import { useEffect, useRef, useState } from 'react';
import {
    Link,
    useNavigate,
    useParams,
    useSearchParams,
} from 'react-router-dom';
import { toast } from 'react-toastify';
import { orderApi } from '../api/services';
import { ApiError, fieldErrors } from '../api/client';
import { acquireInvoicePdf } from '../api/invoicePdf';
import { Alert, Button, EmptyState, Field, Loader, Pagination } from '../components/ui';
import { PdfDownloader } from '../components/PdfDownloader';
import { useAuth } from '../hooks/useAuth';
import { useOrder } from '../hooks/useOrder';
import { formatDate, formatPrice } from '../utils/format';

const NEXT_STATUS = {
    pending: { value: 'processing', label: 'Processing' },
    processing: { value: 'shipped', label: 'Shipped' },
    shipped: { value: 'delivered', label: 'Delivered' },
};
const orderLabel = (order) => order.order_number || String(order.id);

function StaffStatusControl({ order, updating, onUpdate }) {
    const [open, setOpen] = useState(false);
    const [pendingStatus, setPendingStatus] = useState(null);
    const [trackingNumber, setTrackingNumber] = useState('');
    const [courier, setCourier] = useState('');
    const dropdownRef = useRef(null);
    const confirmButtonRef = useRef(null);
    const next = NEXT_STATUS[order.status];
    const canCancel = ['pending', 'processing'].includes(order.status);
    const options = [next, canCancel ? { value: 'cancelled', label: 'Cancelled' } : null].filter(Boolean);
    useEffect(() => {
        if (!open && !pendingStatus)
            return undefined;
        const closeDropdown = (event) => {
            if (event.type === 'keydown') {
                if (event.key !== 'Escape')
                    return;
                setOpen(false);
                setPendingStatus(null);
                return;
            }
            if (event.type === 'mousedown' && dropdownRef.current?.contains(event.target))
                return;
            setOpen(false);
        };
        document.addEventListener('mousedown', closeDropdown);
        document.addEventListener('keydown', closeDropdown);
        return () => {
            document.removeEventListener('mousedown', closeDropdown);
            document.removeEventListener('keydown', closeDropdown);
        };
    }, [open, pendingStatus]);
    useEffect(() => {
        if (pendingStatus)
            confirmButtonRef.current?.focus();
    }, [pendingStatus]);
    return <div className="staff-bootstrap-dropdown" ref={dropdownRef} onClick={(event) => event.stopPropagation()}>
      <button type="button" className={`staff-status-select status--${order.status}`} aria-label={`Status for order ${orderLabel(order)}`} aria-haspopup="menu" aria-expanded={open} disabled={updating || !options.length} onClick={() => setOpen((current) => !current)}>
        {updating ? 'Updating…' : order.status}<span className="staff-dropdown-caret" aria-hidden="true"/>
      </button>
      <div className={`staff-dropdown-menu${open ? ' show' : ''}`} role="menu">
        {options.map((option) => <button type="button" className={`staff-dropdown-item${option.value === 'cancelled' ? ' is-danger' : ''}`} role="menuitem" key={option.value} onClick={() => { setOpen(false); setPendingStatus(option.value); }}>{option.label}</button>)}
      </div>
      {pendingStatus && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setPendingStatus(null); }}>
        <section className="confirm-modal staff-status-confirm" role="dialog" aria-modal="true" aria-labelledby={`status-confirm-title-${order.id}`} aria-describedby={`status-confirm-description-${order.id}`}>
          <p className="eyebrow">Confirm status change</p>
          <h2 id={`status-confirm-title-${order.id}`}>Update order {orderLabel(order)}?</h2>
          <p id={`status-confirm-description-${order.id}`}>This order will move from <strong>{order.status}</strong> to <strong>{pendingStatus}</strong>.</p>
          {pendingStatus === 'shipped' && <><Field label="Courier" name={`courier-${order.id}`} value={courier} onChange={(event) => setCourier(event.target.value)} placeholder="Courier name"/><Field label="Tracking number" name={`tracking-${order.id}`} required value={trackingNumber} onChange={(event) => setTrackingNumber(event.target.value)} placeholder="Carrier tracking number"/></>}
          <div className="confirm-modal__actions">
            <Button type="button" variant="secondary" onClick={() => setPendingStatus(null)}>Cancel</Button>
            <Button ref={confirmButtonRef} type="button" disabled={pendingStatus === 'shipped' && !trackingNumber.trim()} onClick={() => { const status = pendingStatus; const tracking_number = trackingNumber.trim(); const courier_name = courier.trim(); setPendingStatus(null); setTrackingNumber(''); setCourier(''); onUpdate(status, tracking_number ? { tracking_number, courier: courier_name } : {}); }}>Confirm update</Button>
          </div>
        </section>
      </div>}
    </div>;
}
const profileForm = (user) => ({
    email: user?.email || '', first_name: user?.first_name || '', last_name: user?.last_name || '',
    phone: user?.phone || '', address: user?.address || '', city: user?.city || '',
    postal_code: user?.postal_code || '', country: user?.country || '', current_password: '',
});

export function AccountPage() {
    const { user, updateProfile } = useAuth();
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [form, setForm] = useState(() => profileForm(user));
    const [errors, setErrors] = useState({});
    const emailChanged = form.email.trim().toLowerCase() !== (user?.email || '').toLowerCase();
    const change = (field) => (event) => setForm({ ...form, [field]: event.target.value });
    const cancel = () => { setForm(profileForm(user)); setErrors({}); setEditing(false); };
    const submit = async (event) => {
        event.preventDefault();
        const validation = {};
        if (!form.email.includes('@')) validation.email = 'Enter a valid email address.';
        if (emailChanged && !form.current_password) validation.current_password = 'Enter your current password.';
        if (Object.keys(validation).length) { setErrors(validation); return; }
        setSaving(true);
        setErrors({});
        const optional = ['first_name', 'last_name', 'phone', 'address', 'city', 'postal_code', 'country'];
        const payload = { email: form.email.trim() };
        optional.forEach((field) => { payload[field] = form[field].trim() || null; });
        if (emailChanged) payload.current_password = form.current_password;
        try {
            const updated = await updateProfile(payload);
            setForm(profileForm(updated));
            setEditing(false);
            toast.success('Profile updated successfully.');
        }
        catch (reason) {
            setErrors(reason instanceof ApiError ? fieldErrors(reason.data) : { detail: 'Unable to update your profile.' });
        }
        finally { setSaving(false); }
    };
    return <div className="container page"><div className="page-heading"><div><p className="eyebrow">Your account</p><h1>Hello, {user?.first_name || user?.username}</h1><p>Review your profile and keep track of every order.</p></div></div>
    <div className="account-grid">{editing ? <form className="account-card profile-form-card" onSubmit={submit}><div className="profile-card-heading"><h2>Edit profile</h2><button type="button" onClick={cancel}>Cancel</button></div>{errors.detail && <Alert>{errors.detail}</Alert>}<div className="profile-form-grid">
      <Field label="First name" name="first_name" autoComplete="given-name" value={form.first_name} error={errors.first_name} onChange={change('first_name')}/><Field label="Last name" name="last_name" autoComplete="family-name" value={form.last_name} error={errors.last_name} onChange={change('last_name')}/><Field label="Email" name="email" type="email" autoComplete="email" required value={form.email} error={errors.email} onChange={change('email')}/><Field label="Phone" name="phone" type="tel" autoComplete="tel" value={form.phone} error={errors.phone} onChange={change('phone')}/><Field label="Street address" name="address" autoComplete="street-address" value={form.address} error={errors.address} onChange={change('address')}/><Field label="City" name="city" autoComplete="address-level2" value={form.city} error={errors.city} onChange={change('city')}/><Field label="Postal code" name="postal_code" autoComplete="postal-code" value={form.postal_code} error={errors.postal_code} onChange={change('postal_code')}/><Field label="Country" name="country" autoComplete="country-name" value={form.country} error={errors.country} onChange={change('country')}/>{emailChanged && <Field label="Current password" name="current_password" type="password" autoComplete="current-password" required value={form.current_password} error={errors.current_password} hint="Required to change your email address." onChange={change('current_password')}/>}</div><Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save profile'}</Button></form> : <section className="account-card"><span className="account-card__icon">◎</span><div className="profile-card-heading"><h2>Profile</h2><button type="button" onClick={() => setEditing(true)}>Edit</button></div><dl><div><dt>Username</dt><dd>{user?.username}</dd></div><div><dt>Email</dt><dd>{user?.email}</dd></div><div><dt>Name</dt><dd>{[user?.first_name, user?.last_name].filter(Boolean).join(' ') || 'Not provided'}</dd></div><div><dt>Phone</dt><dd>{user?.phone || 'Not provided'}</dd></div><div><dt>Address</dt><dd>{[user?.address, user?.city, user?.postal_code, user?.country].filter(Boolean).join(', ') || 'Not provided'}</dd></div></dl></section>}
      <Link className="account-card account-card--link" to={user?.can_manage_orders ? '/staff/orders' : '/account/orders'}><span className="account-card__icon">▤</span><h2>{user?.can_manage_orders ? 'Manage orders' : 'Order history'}</h2><p>{user?.can_manage_orders ? 'Review customer orders and advance fulfillment status.' : 'See order totals, products, dates, and current status.'}</p><strong>{user?.can_manage_orders ? 'Open order management' : 'View your orders'} →</strong></Link></div>
  </div>;
}
export function OrdersPage() {
    const { user } = useAuth();
    const isStaff = Boolean(user?.can_manage_orders);
    const navigate = useNavigate();
    const [params, setParams] = useSearchParams();
    const page = Number(params.get('page') || 1);
    const status = (params.get('status') || '');
    const view = params.get('view') || 'orders';
    const [orders, setOrders] = useState([]);
    const [count, setCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [receiptOrder, setReceiptOrder] = useState(null);
    const [updatingId, setUpdatingId] = useState(null);
    useEffect(() => {
        if (isStaff && view !== 'orders')
            return;
        setLoading(true);
        setError('');
        orderApi.list(page, status).then((data) => { setOrders(data.results); setCount(data.count); }).catch((reason) => setError(reason.message)).finally(() => setLoading(false));
    }, [isStaff, page, status, view]);
    const update = (key, value) => {
        const next = new URLSearchParams(params);
        if (value)
            next.set(key, value);
        else
            next.delete(key);
        if (key !== 'page')
            next.delete('page');
        setParams(next);
    };
    const openReceipt = (orderId) => {
        navigate(`${isStaff ? '/staff/orders' : '/account/orders'}/${orderId}`);
    };
    const handleRowKeyDown = (event, orderId) => {
        if (event.target !== event.currentTarget)
            return;
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openReceipt(orderId);
        }
    };
    const updateStatus = async (order, nextStatus, extra = {}) => {
        setUpdatingId(order.id);
        setError('');
        try {
            const updated = await orderApi.updateStatus(order.id, nextStatus, extra);
            setOrders((current) => current.map((item) => item.id === updated.id ? updated : item));
            toast.success(`Order ${orderLabel(order)} is now ${updated.status}.`);
        }
        catch (reason) { setError(reason.message); }
        finally { setUpdatingId(null); }
    };
    if (isStaff && view !== 'orders')
        return <div className="container page staff-orders-page"><div className="page-heading"><div><p className="eyebrow">Staff workspace</p><h1>Manage orders</h1><p>Returns and full Stripe refunds.</p></div></div><StaffOrderNav view={view} status={status} onSelect={(nextView, nextStatus = '') => setParams(nextView === 'orders' ? (nextStatus ? { status: nextStatus } : {}) : { view: nextView })}/><StaffRequestsPanel view={view}/></div>;
    return <div className="container page staff-orders-page"><div className="page-heading"><div><p className="eyebrow">{isStaff ? 'Staff workspace' : 'Your account'}</p><h1>{isStaff ? 'Manage orders' : 'Order history'}</h1><p>{count} {isStaff ? 'customer ' : ''}{count === 1 ? 'order' : 'orders'}</p></div>{!isStaff && <label className="status-filter">Status<select value={status} onChange={(e) => update('status', e.target.value)}><option value="">All orders</option><option value="pending">Pending</option><option value="processing">Processing</option><option value="shipped">Shipped</option><option value="delivered">Delivered</option><option value="cancelled">Cancelled</option></select></label>}</div>
    {isStaff && <StaffOrderNav view={view} status={status} onSelect={(nextView, nextStatus = '') => setParams(nextView === 'orders' ? (nextStatus ? { status: nextStatus } : {}) : { view: nextView })}/>} 
    {error ? <Alert>{error}</Alert> : loading ? <Loader label="Loading orders"/> : orders.length ? <div className="order-table-wrap">
      <table className={`order-table ${isStaff ? 'staff-order-table' : ''}`}>
        <thead><tr><th scope="col">Order</th>{isStaff && <th scope="col">Customer</th>}<th scope="col">Date</th><th scope="col">Items</th><th scope="col">Status</th>{isStaff && <th scope="col">Payment</th>}<th scope="col">Total</th><th scope="col">{isStaff ? 'Actions' : <span className="sr-only">Action</span>}</th></tr></thead>
        <tbody>{orders.map((order) => <tr key={order.id} role="link" tabIndex={0} aria-label={`View order ${orderLabel(order)}`} onClick={() => openReceipt(order.id)} onKeyDown={(event) => handleRowKeyDown(event, order.id)}>
          <th scope="row" data-label="Order">{orderLabel(order)}</th>
          {isStaff && <td data-label="Customer"><strong>{order.customer?.username}</strong><span className="staff-customer-email">{order.customer?.email || 'No email'}</span></td>}
          <td data-label="Date">{formatDate(order.created_at)}</td>
          <td data-label="Items">{order.items.length} {order.items.length === 1 ? 'item' : 'items'}</td>
          <td data-label="Status">{isStaff ? <StaffStatusControl order={order} updating={updatingId === order.id} onUpdate={(nextStatus, extra) => void updateStatus(order, nextStatus, extra)}/> : <span className={`status status--${order.status}`}>{order.status}</span>}</td>
          {isStaff && <td data-label="Payment"><span className={`payment-status payment-status--${order.payment_status}`}>{order.payment_status}</span></td>}
          <td data-label="Total"><strong>{formatPrice(order.total)}</strong></td>
          {isStaff ? <td className="order-table__action"><button type="button" onClick={(event) => { event.stopPropagation(); openReceipt(order.id); }}>View</button></td> : <td className="order-table__action"><button type="button" disabled={!order.invoice} onClick={(event) => { event.stopPropagation(); if (order.invoice) setReceiptOrder(order); }}>{order.invoice ? (order.invoice.pdf_generated_at ? 'View invoice' : 'Prepare invoice') : 'Invoice unavailable'} <span aria-hidden="true">→</span></button></td>}
        </tr>)}</tbody>
      </table>
    </div> : <EmptyState title={isStaff ? 'No matching orders' : 'No orders yet'} action={!isStaff && <Link className="button button--primary" to="/products">Start shopping</Link>}>{isStaff ? 'Try another status filter.' : 'Orders you place will appear here.'}</EmptyState>}
    <Pagination page={page} count={count} onPage={(next) => update('page', String(next))}/>
    {receiptOrder && <ReceiptPdfModal order={receiptOrder} onClose={() => setReceiptOrder(null)}/>}
  </div>;
}
export function OrderDetailPage() {
    const { id = '' } = useParams();
    const { user } = useAuth();
    const isStaff = Boolean(user?.can_manage_orders);
    const { order, setOrder, loading, error, setError } = useOrder(id);
    const [updating, setUpdating] = useState(false);
    const [receiptOrder, setReceiptOrder] = useState(null);
    const [returnOpen, setReturnOpen] = useState(false);
    const updateStatus = async (nextStatus, extra = {}) => {
        setUpdating(true);
        setError('');
        try {
            const updated = await orderApi.updateStatus(order.id, nextStatus, extra);
            setOrder(updated);
            toast.success(`Order ${orderLabel(order)} is now ${updated.status}.`);
        }
        catch (reason) { setError(reason.message); }
        finally { setUpdating(false); }
    };
    const ordersPath = isStaff ? '/staff/orders' : '/account/orders';
    const runAction = async (action) => { setUpdating(true); try { if (action === 'refund') { await orderApi.refund(order.id); toast.success('Full refund approved.'); } else { await orderApi.sendEmail(order.id); toast.success('Status email sent.'); } setOrder(await orderApi.detail(order.id)); } catch (reason) { if (!(reason instanceof ApiError)) toast.error(reason.message); } finally { setUpdating(false); } };
    return <div className="container page staff-order-detail-page"><nav className="breadcrumbs"><Link to={ordersPath}>{isStaff ? 'Manage orders' : 'Order history'}</Link><span>/</span><span>Order {order ? orderLabel(order) : id}</span></nav>{loading ? <Loader /> : error ? <Alert>{error}</Alert> : order && <div className="receipt"><header className="receipt__header"><div><p className="eyebrow">{isStaff ? 'Customer order' : 'Order receipt'}</p><h1>{isStaff ? 'Order' : 'Receipt'} {orderLabel(order)}</h1><p>Placed {formatDate(order.created_at)}</p></div><div className="staff-status-control">{isStaff ? <StaffStatusControl order={order} updating={updating} onUpdate={(nextStatus, extra) => void updateStatus(nextStatus, extra)}/> : <span className={`status status--${order.status}`}>{order.status}</span>}</div></header>{isStaff && <StaffOrderActions order={order} disabled={updating} onInvoice={() => setReceiptOrder(order)} onRefund={() => void runAction('refund')} onEmail={() => void runAction('email')}/>}<OrderInformation order={order} isStaff={isStaff}/><OrderDetailContent order={order}/><OrderTimeline order={order}/>{!isStaff && order.status === 'delivered' && order.payment_status === 'paid' && !order.return_request && <Button onClick={() => setReturnOpen(true)}>Request a return</Button>}{order.return_request && <Alert kind="info">Return request: {order.return_request.status}. {order.return_request.staff_note}</Alert>}<Link className="receipt__back text-link" to={ordersPath}>← Back to {isStaff ? 'order management' : 'order history'}</Link>{receiptOrder && <ReceiptPdfModal order={receiptOrder} onClose={() => setReceiptOrder(null)}/>} {returnOpen && <ReturnRequestModal order={order} onClose={() => setReturnOpen(false)} onSaved={async () => { setReturnOpen(false); setOrder(await orderApi.detail(order.id)); }}/>}</div>}</div>;
}
export function OrderDetailContent({ order }) {
    return <section className="receipt__body">
      <div className="receipt-table-wrap">
        <table className="receipt-table">
          <thead><tr><th scope="col">Item</th><th scope="col">Unit price</th><th scope="col">Quantity</th><th scope="col">Line total</th></tr></thead>
          <tbody>{order.items.map((item) => <tr key={item.id}>
            <th scope="row" data-label="Item">{item.product_name}</th>
            <td data-label="Unit price">{formatPrice(item.unit_price)}</td>
            <td data-label="Quantity">{item.quantity}</td>
            <td data-label="Line total"><strong>{formatPrice(item.line_total)}</strong></td>
          </tr>)}</tbody>
          <tfoot><tr><th scope="row" colSpan="3">Order total</th><td><strong>{formatPrice(order.total)}</strong></td></tr></tfoot>
        </table>
      </div>
      <dl className="receipt__summary">
        <div><dt>Order number</dt><dd>{orderLabel(order)}</dd></div>
        <div><dt>Date</dt><dd>{formatDate(order.created_at)}</dd></div>
        <div><dt>Status</dt><dd><span className={`status status--${order.status}`}>{order.status}</span></dd></div>
        <div className="receipt__summary-total"><dt>Order total</dt><dd>{formatPrice(order.total)}</dd></div>
      </dl>
    </section>;
}

function StaffOrderNav({ view, status, onSelect }) {
    const items = [
        ['orders', '', 'All orders'],
        ['orders', 'pending', 'Pending'],
        ['orders', 'processing', 'Processing'],
        ['orders', 'shipped', 'Shipped'],
        ['orders', 'delivered', 'Delivered'],
        ['orders', 'cancelled', 'Cancelled'],
        ['returns', '', 'Returns'],
        ['refunds', '', 'Refunds'],
    ];
    return <nav className="staff-order-tabs" aria-label="Order management sections">{items.map(([itemView, itemStatus, label]) => <button type="button" key={`${itemView}-${itemStatus}`} className={view === itemView && status === itemStatus ? 'active' : ''} onClick={() => onSelect(itemView, itemStatus)}>{label}</button>)}</nav>;
}

function StaffRequestsPanel({ view }) {
    const [page, setPage] = useState(1);
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const load = async () => {
        setData(null); setError('');
        try { setData(view === 'returns' ? await orderApi.returns(page) : await orderApi.refunds(page)); }
        catch (reason) { setError(reason.message); }
    };
    useEffect(() => { void load(); }, [page, view]); // eslint-disable-line react-hooks/exhaustive-deps
    const updateReturn = async (request, nextStatus) => {
        try { await orderApi.updateReturn(request.id, { status: nextStatus }); toast.success(`Return ${nextStatus}.`); await load(); }
        catch (reason) { if (!(reason instanceof ApiError)) toast.error(reason.message); }
    };
    if (error) return <Alert>{error}</Alert>;
    if (!data) return <Loader label={`Loading ${view}`}/>;
    if (!data.results.length) return <EmptyState title={`No ${view}`}>Requests will appear here when available.</EmptyState>;
    return <><div className="staff-product-table-wrap"><table className="staff-product-table order-request-table"><thead><tr><th>Order</th><th>Customer</th><th>{view === 'returns' ? 'Reason' : 'Amount'}</th><th>Status</th><th>Date</th>{view === 'returns' && <th>Actions</th>}</tr></thead><tbody>{data.results.map((request) => <tr key={request.id}><th><Link to={`/staff/orders/${request.order}`}>{request.order_number}</Link></th><td>{request.customer}</td><td>{view === 'returns' ? request.reason : formatPrice(request.amount)}</td><td><span className={`catalog-state catalog-state--${request.status}`}>{request.status}</span></td><td>{formatDate(request.created_at)}</td>{view === 'returns' && <td><div className="return-actions">{request.status === 'requested' && <><button onClick={() => void updateReturn(request, 'approved')}>Approve</button><button className="danger-link" onClick={() => void updateReturn(request, 'rejected')}>Reject</button></>}{request.status === 'approved' && <button onClick={() => void updateReturn(request, 'received')}>Mark received</button>}</div></td>}</tr>)}</tbody></table></div><Pagination page={page} count={data.count} onPage={setPage}/></>;
}

function StaffOrderActions({ order, disabled, onInvoice, onRefund, onEmail }) {
    return <div className="staff-order-actions"><Button variant="secondary" disabled={!order.invoice} onClick={onInvoice}>Print invoice</Button><Button variant="secondary" disabled={disabled} onClick={onEmail}>Send email</Button><Button variant="danger" disabled={disabled || order.payment_status !== 'paid'} onClick={onRefund}>{order.payment_status === 'refunded' ? 'Refunded' : 'Full refund'}</Button></div>;
}

function OrderInformation({ order, isStaff }) {
    const provider = order.payment_provider
        ? order.payment_provider.charAt(0).toUpperCase() + order.payment_provider.slice(1)
        : order.payment_method || 'Not provided';
    return <div className="order-information-grid">{isStaff && <section><h2>Customer info</h2><dl><div><dt>Username</dt><dd>{order.customer?.username}</dd></div><div><dt>Email</dt><dd>{order.billing_email || order.customer?.email || 'Not provided'}</dd></div><div><dt>Name</dt><dd>{order.billing_name || 'Not provided'}</dd></div></dl></section>}<section><h2>Shipping address</h2><address>{order.address || 'Not provided'}<br/>{[order.city, order.postal_code].filter(Boolean).join(', ')}<br/>{order.country}</address></section><section><h2>Payment & delivery</h2><dl><div><dt>Payment method</dt><dd>{provider}</dd></div><div><dt>Payment status</dt><dd>{order.payment_status}</dd></div><div><dt>Courier</dt><dd>{order.courier || 'Not assigned'}</dd></div><div><dt>Tracking number</dt><dd>{order.tracking_number || 'Not assigned'}</dd></div><div><dt>Invoice</dt><dd>{order.invoice?.invoice_number || 'Unavailable'}</dd></div></dl></section></div>;
}

function OrderTimeline({ order }) {
    const events = [{ id: 'placed', event_type: 'order_placed', description: 'Order placed.', created_at: order.created_at }, ...(order.timeline || [])];
    return <section className="order-timeline"><h2>Order timeline</h2><ol>{events.map((event) => <li key={event.id}><span/><div><strong>{event.description}</strong><time dateTime={event.created_at}>{formatDate(event.created_at)}</time>{event.created_by && <small>by {event.created_by}</small>}</div></li>)}</ol></section>;
}

function ReturnRequestModal({ order, onClose, onSaved }) {
    const [reason, setReason] = useState(''); const [saving, setSaving] = useState(false); const [error, setError] = useState('');
    const submit = async (event) => { event.preventDefault(); setSaving(true); setError(''); try { await orderApi.requestReturn(order.id, reason); toast.success('Return request submitted.'); await onSaved(); } catch (failure) { setError(failure.message); } finally { setSaving(false); } };
    return <div className="modal-backdrop"><section className="confirm-modal return-request-modal" role="dialog" aria-modal="true"><p className="eyebrow">Return request</p><h2>Return order {orderLabel(order)}</h2><p>Explain why you want to return this order.</p>{error && <Alert>{error}</Alert>}<form onSubmit={submit}><label className="field"><span>Reason</span><textarea rows="5" minLength="10" required value={reason} onChange={(event) => setReason(event.target.value)}/></label><div className="confirm-modal__actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Submitting…' : 'Submit request'}</Button></div></form></section></div>;
}

function ReceiptPdfModal({ order, onClose }) {
    const closeButton = useRef(null);
    const [pdfUrl, setPdfUrl] = useState('');
    const [pdfError, setPdfError] = useState('');
    useEffect(() => {
        closeButton.current?.focus();
        let url = '';
        let cancelled = false;
        const request = acquireInvoicePdf(order.invoice.download_url);
        const loadInvoice = async () => {
            try {
                const blob = await request.promise;
                url = URL.createObjectURL(blob);
                if (!cancelled)
                    setPdfUrl(url);
            }
            catch (reason) {
                if (!cancelled)
                    setPdfError(reason instanceof Error ? reason.message : 'Unable to load invoice.');
            }
        };
        void loadInvoice();
        const handleKeyDown = (event) => {
            if (event.key === 'Escape')
                onClose();
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => {
            cancelled = true;
            if (url)
                URL.revokeObjectURL(url);
            request.release();
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [onClose, order]);
    return <div className="modal-backdrop receipt-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="receipt-modal" role="dialog" aria-modal="true" aria-labelledby="pdf-receipt-title">
        <header className="receipt-modal__header">
          <div><p className="eyebrow">PDF receipt</p><h2 id="pdf-receipt-title">Order {orderLabel(order)}</h2></div>
          <button ref={closeButton} className="receipt-modal__close" type="button" aria-label="Close receipt" onClick={onClose}>×</button>
        </header>
        <div className="receipt-modal__preview">
          {pdfError ? <Alert>{pdfError}</Alert> : pdfUrl ? <iframe src={`${pdfUrl}#toolbar=0&navpanes=0`} title={`PDF invoice for order ${order.id}`}/> : <Loader label="Loading secure invoice"/>}
        </div>
        <footer className="receipt-modal__actions">
          <button className="button button--secondary" type="button" onClick={onClose}>Close</button>
          <PdfDownloader
            pdfUrl={pdfUrl}
            fileName={`${order.invoice.invoice_number}.pdf`}
            title="Download invoice"
            description={`${order.invoice.invoice_number} is ready.`}
            compact
          />
        </footer>
      </section>
    </div>;
}
