import { useEffect, useState } from 'react';
import { FiHeart, FiMapPin, FiMessageSquare, FiSearch, FiShoppingBag, FiUser } from 'react-icons/fi';
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom';
import { customerApi } from '../api/services';
import { Alert, EmptyState, Loader, Pagination } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { formatDate, formatPrice } from '../utils/format';

export function CustomerManagementPage() {
    const { user } = useAuth();
    const [params, setParams] = useSearchParams();
    const page = Number(params.get('page') || 1);
    const [customers, setCustomers] = useState([]);
    const [count, setCount] = useState(0);
    const [search, setSearch] = useState(params.get('search') || '');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    useEffect(() => {
        if (!user?.can_manage_orders)
            return;
        setLoading(true);
        setError('');
        customerApi.list({ page, search: params.get('search') || undefined, status: params.get('status') || undefined })
            .then((data) => { setCustomers(data.results); setCount(data.count); })
            .catch((reason) => setError(reason.message))
            .finally(() => setLoading(false));
    }, [page, params, user]);
    if (!user?.can_manage_orders)
        return <Navigate to="/account" replace/>;
    const updateQuery = (values) => {
        const next = new URLSearchParams(params);
        Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
        if (!('page' in values)) next.delete('page');
        setParams(next);
    };
    return <div className="staff-customer-page container page">
      <div className="page-heading"><div><p className="eyebrow">Customer management</p><h1>All customers</h1><p>{count} registered {count === 1 ? 'customer' : 'customers'}</p></div></div>
      <div className="staff-catalog-toolbar customer-toolbar"><form role="search" onSubmit={(event) => { event.preventDefault(); updateQuery({ search: search.trim() }); }}><FiSearch aria-hidden="true"/><input aria-label="Search customers" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, email, or phone"/><button type="submit">Search</button></form><label>Status<select value={params.get('status') || ''} onChange={(event) => updateQuery({ status: event.target.value })}><option value="">All customers</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label></div>
      {error ? <Alert>{error}</Alert> : loading ? <Loader label="Loading customers"/> : customers.length ? <div className="staff-product-table-wrap"><table className="staff-product-table customer-table"><thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Orders</th><th>Total spent</th><th>Status</th><th><span className="sr-only">Profile</span></th></tr></thead><tbody>{customers.map((customer) => <tr key={customer.id}><th scope="row"><div className="customer-identity"><span>{customer.name.slice(0, 1).toUpperCase()}</span><div><strong>{customer.name}</strong><small>@{customer.username}</small></div></div></th><td>{customer.email || 'Not provided'}</td><td>{customer.phone || 'Not provided'}</td><td>{customer.orders}</td><td><strong>{formatPrice(customer.total_spent)}</strong></td><td><span className={`catalog-state catalog-state--${customer.status}`}>{customer.status}</span></td><td><Link className="text-link" to={`/staff/customers/${customer.id}`}>View profile</Link></td></tr>)}</tbody></table></div> : <EmptyState title="No customers found">Try another search or status filter.</EmptyState>}
      <Pagination page={page} count={count} onPage={(next) => updateQuery({ page: String(next) })}/>
    </div>;
}

export function CustomerProfilePage() {
    const { user } = useAuth();
    const { id = '' } = useParams();
    const [customer, setCustomer] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    useEffect(() => {
        if (!user?.can_manage_orders)
            return;
        customerApi.detail(id).then(setCustomer).catch((reason) => setError(reason.message)).finally(() => setLoading(false));
    }, [id, user]);
    if (!user?.can_manage_orders)
        return <Navigate to="/account" replace/>;
    if (loading)
        return <div className="container page"><Loader label="Loading customer profile"/></div>;
    if (error || !customer)
        return <div className="container page"><Alert>{error || 'Customer not found.'}</Alert></div>;
    const details = customer.personal_details;
    return <div className="staff-customer-page customer-profile-page container page">
      <nav className="breadcrumbs"><Link to="/staff/customers">Customers</Link><span>/</span><span>{customer.name}</span></nav>
      <header className="customer-profile-hero"><span>{customer.name.slice(0, 1).toUpperCase()}</span><div><p className="eyebrow">Customer profile</p><h1>{customer.name}</h1><p>{customer.email || 'No email'} · Customer since {formatDate(customer.date_joined)}</p></div><span className={`catalog-state catalog-state--${customer.status}`}>{customer.status}</span></header>
      <div className="customer-profile-grid">
        <ProfileSection icon={<FiUser/>} title="Personal details"><dl className="customer-details"><div><dt>First name</dt><dd>{details.first_name || 'Not provided'}</dd></div><div><dt>Last name</dt><dd>{details.last_name || 'Not provided'}</dd></div><div><dt>Email</dt><dd>{details.email || 'Not provided'}</dd></div><div><dt>Phone</dt><dd>{details.phone || 'Not provided'}</dd></div><div><dt>Total orders</dt><dd>{customer.orders}</dd></div><div><dt>Total spent</dt><dd>{formatPrice(customer.total_spent)}</dd></div></dl></ProfileSection>
        <ProfileSection icon={<FiMapPin/>} title="Saved addresses">{customer.saved_addresses.length ? customer.saved_addresses.map((address, index) => <address className="saved-address" key={index}>{address.address && <span>{address.address}</span>}{address.city && <span>{address.city}</span>}{address.postal_code && <span>{address.postal_code}</span>}{address.country && <span>{address.country}</span>}</address>) : <ProfileEmpty>No saved address is available.</ProfileEmpty>}</ProfileSection>
        <ProfileSection wide icon={<FiShoppingBag/>} title="Order history">{customer.order_history.length ? <div className="customer-orders"><table><thead><tr><th>Order</th><th>Date</th><th>Status</th><th>Payment</th><th>Total</th></tr></thead><tbody>{customer.order_history.map((order) => <tr key={order.id}><th><Link to={`/staff/orders/${order.id}`}>{order.order_number}</Link></th><td>{formatDate(order.created_at)}</td><td><span className={`status status--${order.status}`}>{order.status}</span></td><td><span className={`payment-status payment-status--${order.payment_status}`}>{order.payment_status}</span></td><td><strong>{formatPrice(order.total)}</strong></td></tr>)}</tbody></table></div> : <ProfileEmpty>No orders have been placed.</ProfileEmpty>}</ProfileSection>
        <ProfileSection icon={<FiHeart/>} title="Wishlist"><ProfileEmpty>Wishlist data is not available because the store has no wishlist feature.</ProfileEmpty></ProfileSection>
        <ProfileSection icon={<FiMessageSquare/>} title="Reviews"><ProfileEmpty>Review data is not available because the store has no review feature.</ProfileEmpty></ProfileSection>
      </div>
    </div>;
}

function ProfileSection({ icon, title, wide = false, children }) {
    return <section className={`customer-profile-card${wide ? ' customer-profile-card--wide' : ''}`}><header><span aria-hidden="true">{icon}</span><h2>{title}</h2></header>{children}</section>;
}

function ProfileEmpty({ children }) {
    return <p className="customer-profile-empty">{children}</p>;
}
