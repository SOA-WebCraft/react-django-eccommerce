import { useCallback, useEffect, useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { paymentApi } from '../api/services';
import { Alert, EmptyState, Loader, Pagination } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { formatDate, formatPrice } from '../utils/format';

const TABS = [['transactions', 'Transactions'], ['methods', 'Payment methods'], ['refunds', 'Refunds'], ['reports', 'Payout reports']];

export function PaymentsPage() {
    const { user } = useAuth();
    const [params, setParams] = useSearchParams();
    const tab = params.get('view') || 'transactions';
    if (!user?.can_manage_orders)
        return <Navigate to="/account" replace/>;
    return <div className="container page payments-page">
      <div className="page-heading"><div><p className="eyebrow">Money management</p><h1>Payments</h1><p>Transactions, payment methods, refunds, and internal revenue summaries.</p></div></div>
      <nav className="staff-order-tabs" aria-label="Payment sections">{TABS.map(([value, label]) => <button type="button" className={tab === value ? 'active' : ''} key={value} onClick={() => setParams(value === 'transactions' ? {} : { view: value })}>{label}</button>)}</nav>
      {tab === 'transactions' && <Transactions/>}
      {tab === 'methods' && <Methods/>}
      {tab === 'refunds' && <Refunds/>}
      {tab === 'reports' && <Reports/>}
    </div>;
}

function Transactions() {
    const [page, setPage] = useState(1); const [data, setData] = useState(null); const [error, setError] = useState('');
    const [filters, setFilters] = useState({ provider: '', method: '', status: '', search: '' });
    const load = useCallback(async () => { setError(''); try { setData(await paymentApi.transactions({ ...filters, page })); } catch (reason) { setError(reason.message); } }, [filters, page]);
    useEffect(() => { void load(); }, [load]);
    return <section>{error && <Alert>{error}</Alert>}<div className="payment-filters"><input aria-label="Search transaction or order" placeholder="Search transaction or order" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })}/><select aria-label="Provider" value={filters.provider} onChange={(e) => setFilters({ ...filters, provider: e.target.value })}><option value="">All providers</option><option value="stripe">Stripe</option><option value="paystack">Paystack</option><option value="paypal">PayPal</option></select><select aria-label="Status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}><option value="">All statuses</option><option value="pending">Pending</option><option value="paid">Paid</option><option value="failed">Failed</option><option value="refunded">Refunded</option></select></div>{!data ? <Loader label="Loading transactions"/> : data.results.length ? <><div className="staff-product-table-wrap"><table className="staff-product-table"><thead><tr><th>Transaction ID</th><th>Order</th><th>Amount</th><th>Method</th><th>Status</th><th>Date</th></tr></thead><tbody>{data.results.map((item) => <tr key={item.public_id}><th>{item.public_id.slice(0, 12).toUpperCase()}</th><td>{item.order ? <Link to={`/staff/orders/${item.order}`}>{item.order_number}</Link> : 'Pending'}</td><td><strong>{formatMoney(item.store_amount, item.store_currency)}</strong>{item.provider_currency !== item.store_currency && <small>{formatMoney(item.provider_amount, item.provider_currency)}</small>}</td><td><strong>{item.card_brand || label(item.method)}</strong><small>{label(item.provider)}</small></td><td><span className={`payment-status payment-status--${item.status}`}>{item.status}</span></td><td>{formatDate(item.created_at)}</td></tr>)}</tbody></table></div><Pagination page={page} count={data.count} onPage={setPage}/></> : <EmptyState title="No transactions">Payments will appear after checkout starts.</EmptyState>}</section>;
}

function Methods() { const state = useRemote(paymentApi.methods); return <Remote state={state}>{(data) => <div className="payment-method-grid">{data.results.map((item) => <article key={`${item.provider}-${item.method}`}><span className={`catalog-state catalog-state--${item.enabled ? 'active' : 'inactive'}`}>{item.enabled ? 'Enabled' : 'Not configured'}</span><h2>{item.label}</h2><p>{item.description}</p><strong>{item.transactions} transactions</strong></article>)}</div>}</Remote>; }
const loadRefunds = () => paymentApi.refunds();
function Refunds() { const state = useRemote(loadRefunds); return <Remote state={state}>{(data) => data.results.length ? <div className="staff-product-table-wrap"><table className="staff-product-table"><thead><tr><th>Order</th><th>Customer</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead><tbody>{data.results.map((item) => <tr key={item.id}><th><Link to={`/staff/orders/${item.order}`}>{item.order_number}</Link></th><td>{item.customer}</td><td>{formatPrice(item.amount)}</td><td>{item.status}</td><td>{formatDate(item.created_at)}</td></tr>)}</tbody></table></div> : <EmptyState title="No refunds">Completed and failed refund requests appear here.</EmptyState>}</Remote>; }
function Reports() { const state = useRemote(paymentApi.reports); return <Remote state={state}>{(data) => <><p className="payment-report-note">Internal summaries only — provider bank settlements may differ.</p><div className="payment-report-grid">{data.currencies.map((row) => <article key={row.currency}><p className="eyebrow">{row.currency} revenue</p><h2>{formatMoney(row.net_revenue, row.currency)}</h2><dl><div><dt>Gross</dt><dd>{formatMoney(row.gross_revenue, row.currency)}</dd></div><div><dt>Refunded</dt><dd>{formatMoney(row.refunded_amount, row.currency)}</dd></div><div><dt>Paid transactions</dt><dd>{row.paid_transactions}</dd></div></dl></article>)}</div></>}</Remote>; }
function useRemote(loader) { const [data, setData] = useState(null); const [error, setError] = useState(''); useEffect(() => { loader().then(setData).catch((reason) => setError(reason.message)); }, [loader]); return { data, error }; }
function Remote({ state, children }) { if (state.error) return <Alert>{state.error}</Alert>; if (!state.data) return <Loader/>; return children(state.data); }
function formatMoney(value, currency) { return new Intl.NumberFormat('en-GH', { style: 'currency', currency }).format(Number(value)); }
function label(value) { return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }
