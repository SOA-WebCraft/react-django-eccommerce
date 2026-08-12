import { useCallback, useEffect, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { catalogApi, discountApi } from '../api/services';
import { Alert, Button, EmptyState, Loader } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { formatDate, formatPrice } from '../utils/format';

const TABS = [['coupons', 'Coupons'], ['promotions', 'Promotions'], ['gift-cards', 'Gift cards']];
const tomorrow = (days) => new Date(Date.now() + days * 86400000).toISOString().slice(0, 16);

export function DiscountsPage() {
    const { user } = useAuth(); const [params, setParams] = useSearchParams(); const tab = params.get('view') || 'coupons';
    if (!user?.can_manage_orders) return <Navigate to="/account" replace/>;
    return <div className="container page discounts-page"><div className="page-heading"><div><p className="eyebrow">Promotions</p><h1>Discounts</h1><p>Manage coupons, scheduled promotions, and secure store gift cards.</p></div></div><nav className="staff-order-tabs" aria-label="Discount sections">{TABS.map(([value, label]) => <button key={value} type="button" className={tab === value ? 'active' : ''} onClick={() => setParams(value === 'coupons' ? {} : { view: value })}>{label}</button>)}</nav>{tab === 'coupons' && <Coupons/>}{tab === 'promotions' && <Promotions/>}{tab === 'gift-cards' && <GiftCards/>}</div>;
}

function Coupons() {
    const [form, setForm] = useState({ code: '', discount_type: 'percentage', value: '10', ends_at: tomorrow(30), usage_limit: '' });
    return <Manager title="Coupons" load={discountApi.coupons} create={() => discountApi.createCoupon({ ...form, code: form.code.toUpperCase(), value: form.value, minimum_subtotal: '0', starts_at: null, ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null, usage_limit: form.usage_limit ? Number(form.usage_limit) : null, is_active: true })} form={<div className="discount-form"><input required placeholder="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })}/><select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })}><option value="percentage">Percentage</option><option value="fixed">Fixed amount</option></select><input required type="number" min="0.01" step="0.01" aria-label="Discount value" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })}/><input type="datetime-local" aria-label="Expiry date" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })}/><input type="number" min="1" placeholder="Usage limit" value={form.usage_limit} onChange={(e) => setForm({ ...form, usage_limit: e.target.value })}/></div>} render={(item) => <><th>{item.code}</th><td>{item.discount_type === 'percentage' ? `${item.value}%` : formatPrice(item.value)}</td><td>{item.ends_at ? formatDate(item.ends_at) : 'No expiry'}</td><td>{item.used_count}/{item.usage_limit || '∞'} <small>{item.reserved_count} reserved</small></td><td><State active={item.is_active}/></td></>} toggle={(item) => discountApi.updateCoupon(item.id, { is_active: !item.is_active })} remove={(item) => discountApi.deleteCoupon(item.id)} headings={['Code', 'Discount', 'Expiry', 'Usage', 'Status']}/>;
}

function Promotions() {
    const [categories, setCategories] = useState([]); const [products, setProducts] = useState([]); const [form, setForm] = useState({ name: '', percentage: '10', scope: 'store', target: '', starts_at: tomorrow(0), ends_at: tomorrow(7) });
    useEffect(() => { catalogApi.categories().then((data) => setCategories(data.results || data)); catalogApi.products().then((data) => setProducts(data.results)); }, []);
    const targets = form.scope === 'categories' ? categories : products;
    return <Manager title="Promotions" load={discountApi.promotions} create={() => discountApi.createPromotion({ name: form.name, percentage: form.percentage, scope: form.scope, categories: form.scope === 'categories' && form.target ? [Number(form.target)] : [], products: form.scope === 'products' && form.target ? [Number(form.target)] : [], starts_at: new Date(form.starts_at).toISOString(), ends_at: new Date(form.ends_at).toISOString(), is_active: true })} form={<div className="discount-form"><input required placeholder="Promotion name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}/><input required type="number" min="0.01" max="100" step="0.01" aria-label="Percentage" value={form.percentage} onChange={(e) => setForm({ ...form, percentage: e.target.value })}/><select value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value, target: '' })}><option value="store">Entire store</option><option value="categories">Category</option><option value="products">Product</option></select>{form.scope !== 'store' && <select required value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })}><option value="">Choose target</option>{targets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}<input required type="datetime-local" aria-label="Starts" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })}/><input required type="datetime-local" aria-label="Ends" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })}/></div>} render={(item) => <><th>{item.name}</th><td>{item.percentage}%</td><td>{item.scope}</td><td>{formatDate(item.starts_at)} – {formatDate(item.ends_at)}</td><td><span className={`catalog-state catalog-state--${item.state}`}>{item.state}</span></td></>} toggle={(item) => discountApi.updatePromotion(item.id, { is_active: !item.is_active })} remove={(item) => discountApi.deletePromotion(item.id)} headings={['Promotion', 'Discount', 'Scope', 'Schedule', 'Status']}/>;
}

function GiftCards() {
    const [form, setForm] = useState({ initial_balance: '100', recipient_email: '', expires_at: tomorrow(365) }); const [issued, setIssued] = useState('');
    const create = async () => {
        const card = await discountApi.createGiftCard({
            initial_balance: form.initial_balance,
            recipient_email: form.recipient_email,
            expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
            is_active: true,
        });
        setIssued(card.code);
        return card;
    };
    const notice = issued ? <Alert kind="success">Copy this gift-card code now. It will not be shown again: <strong>{issued}</strong></Alert> : null;
    const formFields = <div className="discount-form">
      <input required type="number" min="0.01" step="0.01" aria-label="Initial balance" value={form.initial_balance} onChange={(e) => setForm({ ...form, initial_balance: e.target.value })}/>
      <input type="email" placeholder="Recipient email (optional)" value={form.recipient_email} onChange={(e) => setForm({ ...form, recipient_email: e.target.value })}/>
      <input type="datetime-local" aria-label="Expiry" value={form.expires_at} onChange={(e) => setForm({ ...form, expires_at: e.target.value })}/>
    </div>;
    const renderCard = (item) => <>
      <th>{item.masked_code}</th><td>{item.recipient_email || 'Not assigned'}</td>
      <td>{formatPrice(item.current_balance)}<small>{formatPrice(item.reserved_balance)} reserved</small></td>
      <td>{item.expires_at ? formatDate(item.expires_at) : 'No expiry'}</td><td><State active={item.is_active}/></td>
    </>;
    return <Manager title="Gift cards" load={discountApi.giftCards} create={create} notice={notice} form={formFields} render={renderCard} toggle={(item) => discountApi.updateGiftCard(item.id, { is_active: !item.is_active })} headings={['Card', 'Recipient', 'Balance', 'Expiry', 'Status']}/>;
}

function Manager({ title, load, create, form, notice, render, headings, toggle, remove }) {
    const { notify } = useToast(); const [items, setItems] = useState(null); const [error, setError] = useState('');
    const refresh = useCallback(() => load().then((data) => setItems(data.results || data)).catch((reason) => setError(reason.message)), [load]); useEffect(() => { void refresh(); }, [refresh]);
    const submit = async (event) => { event.preventDefault(); setError(''); try { await create(); notify(`${title.slice(0, -1)} created.`, 'success'); await refresh(); } catch (reason) { setError(reason.message); } };
    const act = async (action) => { try { await action(); await refresh(); } catch (reason) { setError(reason.message); } };
    return <section>{notice}{error && <Alert>{error}</Alert>}<form className="discount-create" onSubmit={submit}>{form}<Button type="submit">Create</Button></form>{!items ? <Loader/> : items.length ? <div className="staff-product-table-wrap"><table className="staff-product-table"><thead><tr>{headings.map((heading) => <th key={heading}>{heading}</th>)}<th>Actions</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}>{render(item)}<td><button type="button" className="text-link" onClick={() => void act(() => toggle(item))}>{item.is_active ? 'Deactivate' : 'Activate'}</button>{remove && <button type="button" className="danger-link" onClick={() => void act(() => remove(item))}>Delete</button>}</td></tr>)}</tbody></table></div> : <EmptyState title={`No ${title.toLowerCase()}`}>Create the first one above.</EmptyState>}</section>;
}
function State({ active }) { return <span className={`catalog-state catalog-state--${active ? 'active' : 'inactive'}`}>{active ? 'Active' : 'Inactive'}</span>; }
