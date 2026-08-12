import { useCallback, useEffect, useState } from 'react';
import { FiAlertTriangle, FiArchive, FiEdit3, FiPlus, FiTruck, FiUsers } from 'react-icons/fi';
import { toast } from 'react-toastify';
import { Navigate, useSearchParams } from 'react-router-dom';
import { ApiError, fieldErrors } from '../api/client';
import { catalogApi, inventoryApi } from '../api/services';
import { Alert, Button, EmptyState, Field, Loader, Pagination } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { formatDate, formatPrice } from '../utils/format';

const tabs = [
    ['stock', 'Stock levels'],
    ['movements', 'Stock movements'],
    ['orders', 'Purchase orders'],
    ['suppliers', 'Suppliers'],
];

export function InventoryPage() {
    const { user } = useAuth();
    const [params, setParams] = useSearchParams();
    const tab = params.get('tab') || 'stock';
    if (!user?.can_manage_orders)
        return <Navigate to="/account" replace/>;
    const setTab = (value) => setParams({ tab: value });
    return <div className="inventory-page container page">
      <div className="page-heading"><div><p className="eyebrow">Stock management</p><h1>Inventory</h1><p>Track availability, movements, suppliers, and incoming stock.</p></div></div>
      <nav className="inventory-tabs" aria-label="Inventory sections">{tabs.map(([value, label]) => <button type="button" key={value} className={tab === value ? 'active' : ''} aria-current={tab === value ? 'page' : undefined} onClick={() => setTab(value)}>{label}</button>)}</nav>
      {tab === 'stock' && <StockLevels/>}
      {tab === 'movements' && <StockMovements/>}
      {tab === 'orders' && <PurchaseOrders/>}
      {tab === 'suppliers' && <Suppliers/>}
    </div>;
}

function StockLevels() {
    const [page, setPage] = useState(1);
    const [state, setState] = useState('');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [adjusting, setAdjusting] = useState(null);
    const load = useCallback(() => {
        setLoading(true);
        inventoryApi.stock({ page, state: state || undefined }).then(setData).catch((reason) => setError(reason.message)).finally(() => setLoading(false));
    }, [page, state]);
    useEffect(() => { load(); }, [load]);
    const rows = data?.results || [];
    return <section><div className="inventory-section-heading"><div><h2>Stock levels</h2><p>Reserved stock reflects active checkout sessions.</p></div><label>Show<select value={state} onChange={(event) => { setState(event.target.value); setPage(1); }}><option value="">All stock</option><option value="in_stock">In stock</option><option value="low_stock">Low stock</option><option value="out_of_stock">Out of stock</option></select></label></div>
      <div className="inventory-summary"><SummaryCard icon={<FiArchive/>} label="Products shown" value={rows.length}/><SummaryCard icon={<FiTruck/>} label="Current stock" value={rows.reduce((sum, item) => sum + item.stock_quantity, 0)}/><SummaryCard icon={<FiUsers/>} label="Reserved stock" value={rows.reduce((sum, item) => sum + item.reserved_stock, 0)}/><SummaryCard icon={<FiAlertTriangle/>} label="Low / out" value={rows.filter((item) => item.stock_state !== 'in_stock').length}/></div>
      {error ? <Alert>{error}</Alert> : loading ? <Loader label="Loading stock levels"/> : rows.length ? <div className="staff-product-table-wrap"><table className="staff-product-table inventory-table"><thead><tr><th>Product</th><th>Current</th><th>Reserved</th><th>Available</th><th>Minimum</th><th>Status</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>{rows.map((product) => <tr key={product.id}><th>{product.name}<small>{product.category_name}</small></th><td>{product.stock_quantity}</td><td>{product.reserved_stock}</td><td><strong>{product.available_stock}</strong></td><td>{product.minimum_stock_quantity}</td><td><span className={`inventory-state inventory-state--${product.stock_state}`}>{product.stock_state.replaceAll('_', ' ')}</span></td><td><Button className="inventory-adjust-button" variant="secondary" onClick={() => setAdjusting(product)}><FiEdit3/> Adjust</Button></td></tr>)}</tbody></table></div> : <EmptyState title="No matching inventory">Choose another stock filter.</EmptyState>}
      <Pagination page={page} count={data?.count || 0} onPage={setPage}/>
      {adjusting && <StockAdjustmentModal product={adjusting} onClose={() => setAdjusting(null)} onSaved={() => { setAdjusting(null); load(); }}/>} 
    </section>;
}

function StockAdjustmentModal({ product, onClose, onSaved }) {
    const [form, setForm] = useState({ operation: 'add', quantity: '1', note: '' });
    const [errors, setErrors] = useState({});
    const [saving, setSaving] = useState(false);
    const submit = async (event) => {
        event.preventDefault(); setSaving(true); setErrors({});
        try {
            await inventoryApi.adjust({ product: product.id, operation: form.operation, quantity: Number(form.quantity), note: form.note });
            toast.success(`${product.name} stock updated.`); onSaved();
        }
        catch (reason) { setErrors(reason instanceof ApiError ? fieldErrors(reason.data) : { detail: reason.message }); }
        finally { setSaving(false); }
    };
    return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) onClose(); }}><section className="confirm-modal inventory-form-modal" role="dialog" aria-modal="true" aria-labelledby="adjust-stock-title"><p className="eyebrow">Stock adjustment</p><h2 id="adjust-stock-title">{product.name}</h2><p>Current stock: <strong>{product.stock_quantity}</strong></p>{errors.detail && <Alert>{errors.detail}</Alert>}<form onSubmit={submit}><label className="field"><span>Operation</span><select value={form.operation} onChange={(event) => setForm({ ...form, operation: event.target.value })}><option value="add">Add stock</option><option value="remove">Remove stock</option><option value="set">Set exact stock</option></select></label><Field label="Quantity" name="adjustment-quantity" type="number" min="0" step="1" required value={form.quantity} error={errors.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })}/><Field label="Reason or note" name="adjustment-note" value={form.note} error={errors.note} onChange={(event) => setForm({ ...form, note: event.target.value })}/><div className="confirm-modal__actions"><Button type="button" variant="secondary" disabled={saving} onClick={onClose}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save adjustment'}</Button></div></form></section></div>;
}

function StockMovements() {
    const [page, setPage] = useState(1); const [data, setData] = useState(null); const [error, setError] = useState('');
    useEffect(() => { inventoryApi.movements({ page }).then(setData).catch((reason) => setError(reason.message)); }, [page]);
    if (error) return <Alert>{error}</Alert>;
    if (!data) return <Loader label="Loading stock movements"/>;
    return <section><div className="inventory-section-heading"><div><h2>Stock movements</h2><p>Immutable history of additions, removals, adjustments, and received orders.</p></div></div>{data.results.length ? <div className="staff-product-table-wrap"><table className="staff-product-table inventory-table"><thead><tr><th>Product</th><th>Type</th><th>Change</th><th>Previous</th><th>Result</th><th>Staff</th><th>Date</th></tr></thead><tbody>{data.results.map((movement) => <tr key={movement.id}><th>{movement.product_name}<small>{movement.note || 'No note'}</small></th><td>{movement.movement_type.replaceAll('_', ' ')}</td><td><strong className={movement.quantity_change >= 0 ? 'movement-positive' : 'movement-negative'}>{movement.quantity_change > 0 ? '+' : ''}{movement.quantity_change}</strong></td><td>{movement.previous_stock}</td><td>{movement.resulting_stock}</td><td>{movement.created_by}</td><td>{formatDate(movement.created_at)}</td></tr>)}</tbody></table></div> : <EmptyState title="No stock movements">Adjust inventory or receive a purchase order to create history.</EmptyState>}<Pagination page={page} count={data.count} onPage={setPage}/></section>;
}

function Suppliers() {
    const [data, setData] = useState(null); const [editing, setEditing] = useState(null); const [error, setError] = useState('');
    const load = useCallback(() => inventoryApi.suppliers().then(setData).catch((reason) => setError(reason.message)), []);
    useEffect(() => { load(); }, [load]);
    const remove = async (supplier) => { if (!window.confirm(`Delete supplier ${supplier.name}?`)) return; try { await inventoryApi.deleteSupplier(supplier.id); toast.success('Supplier deleted.'); load(); } catch (reason) { if (!(reason instanceof ApiError)) toast.error(reason.message); } };
    return <section><div className="inventory-section-heading"><div><h2>Suppliers</h2><p>Supplier contact information and supplied products.</p></div><Button onClick={() => setEditing({})}><FiPlus/> Add supplier</Button></div>{error ? <Alert>{error}</Alert> : !data ? <Loader label="Loading suppliers"/> : data.results.length ? <div className="supplier-grid">{data.results.map((supplier) => <article className="supplier-card" key={supplier.id}><div><span><FiTruck/></span><div><h3>{supplier.name}</h3><p>{supplier.product_names.length} products</p></div></div><dl><div><dt>Phone</dt><dd>{supplier.phone || 'Not provided'}</dd></div><div><dt>Email</dt><dd>{supplier.email || 'Not provided'}</dd></div></dl><p>{supplier.product_names.join(', ') || 'No linked products'}</p><footer><button onClick={() => setEditing(supplier)}>Edit</button><button className="danger-link" onClick={() => void remove(supplier)}>Delete</button></footer></article>)}</div> : <EmptyState title="No suppliers">Add a supplier before creating a purchase order.</EmptyState>}{editing && <SupplierModal supplier={editing.id ? editing : null} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }}/>}</section>;
}

function SupplierModal({ supplier, onClose, onSaved }) {
    const [form, setForm] = useState({ name: supplier?.name || '', phone: supplier?.phone || '', email: supplier?.email || '' }); const [saving, setSaving] = useState(false); const [errors, setErrors] = useState({});
    const submit = async (event) => { event.preventDefault(); setSaving(true); try { if (supplier) await inventoryApi.updateSupplier(supplier.id, form); else await inventoryApi.createSupplier(form); toast.success(supplier ? 'Supplier updated.' : 'Supplier created.'); onSaved(); } catch (reason) { setErrors(reason instanceof ApiError ? fieldErrors(reason.data) : { detail: reason.message }); } finally { setSaving(false); } };
    return <div className="modal-backdrop"><section className="confirm-modal inventory-form-modal" role="dialog" aria-modal="true"><p className="eyebrow">Supplier information</p><h2>{supplier ? 'Edit supplier' : 'Add supplier'}</h2>{errors.detail && <Alert>{errors.detail}</Alert>}<form onSubmit={submit}><Field label="Name" name="supplier-name" required value={form.name} error={errors.name} onChange={(event) => setForm({ ...form, name: event.target.value })}/><Field label="Phone" name="supplier-phone" value={form.phone} error={errors.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })}/><Field label="Email" name="supplier-email" type="email" value={form.email} error={errors.email} onChange={(event) => setForm({ ...form, email: event.target.value })}/><div className="confirm-modal__actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save supplier'}</Button></div></form></section></div>;
}

function PurchaseOrders() {
    const [data, setData] = useState(null); const [suppliers, setSuppliers] = useState([]); const [products, setProducts] = useState([]); const [creating, setCreating] = useState(false); const [error, setError] = useState('');
    const load = useCallback(() => inventoryApi.purchaseOrders().then(setData).catch((reason) => setError(reason.message)), []);
    useEffect(() => { load(); inventoryApi.suppliers().then((result) => setSuppliers(result.results)); catalogApi.products({ page: 1 }).then(async (first) => { const pages = Math.ceil(first.count / 20); const rest = await Promise.all(Array.from({ length: Math.max(0, pages - 1) }, (_, index) => catalogApi.products({ page: index + 2 }))); setProducts([first, ...rest].flatMap((page) => page.results)); }); }, [load]);
    const action = async (order, operation) => { if (!window.confirm(`${operation === 'receive' ? 'Receive' : 'Cancel'} purchase order #${order.id}?`)) return; try { if (operation === 'receive') await inventoryApi.receivePurchaseOrder(order.id); else await inventoryApi.cancelPurchaseOrder(order.id); toast.success(`Purchase order ${operation === 'receive' ? 'received' : 'cancelled'}.`); load(); } catch (reason) { if (!(reason instanceof ApiError)) toast.error(reason.message); } };
    return <section><div className="inventory-section-heading"><div><h2>Purchase orders</h2><p>Order products from suppliers and receive them into stock.</p></div><Button disabled={!suppliers.length} onClick={() => setCreating(true)}><FiPlus/> New purchase order</Button></div>{error ? <Alert>{error}</Alert> : !data ? <Loader label="Loading purchase orders"/> : data.results.length ? <div className="purchase-order-list">{data.results.map((order) => <article key={order.id}><header><div><span>PO #{order.id}</span><h3>{order.supplier_name}</h3></div><span className={`catalog-state catalog-state--${order.status}`}>{order.status}</span></header><div className="purchase-order-items">{order.items.map((item) => <span key={item.id}>{item.product_name} × {item.quantity}</span>)}</div><dl><div><dt>Total cost</dt><dd>{formatPrice(order.total_cost)}</dd></div><div><dt>Created</dt><dd>{formatDate(order.created_at)}</dd></div></dl>{order.status === 'ordered' && <footer><Button variant="secondary" onClick={() => void action(order, 'cancel')}>Cancel</Button><Button onClick={() => void action(order, 'receive')}>Receive stock</Button></footer>}</article>)}</div> : <EmptyState title="No purchase orders">Create an order to track incoming stock.</EmptyState>}{creating && <PurchaseOrderModal suppliers={suppliers} products={products} onClose={() => setCreating(false)} onSaved={() => { setCreating(false); load(); }}/>}</section>;
}

function PurchaseOrderModal({ suppliers, products, onClose, onSaved }) {
    const [form, setForm] = useState({ supplier: String(suppliers[0]?.id || ''), notes: '', items: [{ product: '', quantity: '1', unit_cost: '0.00' }] }); const [saving, setSaving] = useState(false); const [errors, setErrors] = useState({});
    const updateItem = (index, field, value) => setForm({ ...form, items: form.items.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item) });
    const submit = async (event) => { event.preventDefault(); setSaving(true); try { await inventoryApi.createPurchaseOrder({ supplier: Number(form.supplier), notes: form.notes, items: form.items.map((item) => ({ product: Number(item.product), quantity: Number(item.quantity), unit_cost: item.unit_cost })) }); toast.success('Purchase order created.'); onSaved(); } catch (reason) { setErrors(reason instanceof ApiError ? fieldErrors(reason.data) : { detail: reason.message }); } finally { setSaving(false); } };
    return <div className="modal-backdrop product-editor-backdrop"><section className="product-editor-modal purchase-order-modal" role="dialog" aria-modal="true"><header><div><p className="eyebrow">Incoming stock</p><h2>New purchase order</h2></div><button onClick={onClose}>×</button></header><form onSubmit={submit}>{errors.detail && <Alert>{errors.detail}</Alert>}<label className="field"><span>Supplier</span><select required value={form.supplier} onChange={(event) => setForm({ ...form, supplier: event.target.value })}>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></label><Field label="Notes" name="purchase-notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })}/><div className="purchase-order-editor-items">{form.items.map((item, index) => <div key={index}><label className="field"><span>Product</span><select required value={item.product} onChange={(event) => updateItem(index, 'product', event.target.value)}><option value="">Choose product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label><Field label="Quantity" name={`po-quantity-${index}`} type="number" min="1" required value={item.quantity} onChange={(event) => updateItem(index, 'quantity', event.target.value)}/><Field label="Unit cost" name={`po-cost-${index}`} type="number" min="0" step="0.01" required value={item.unit_cost} onChange={(event) => updateItem(index, 'unit_cost', event.target.value)}/>{form.items.length > 1 && <button type="button" onClick={() => setForm({ ...form, items: form.items.filter((_, itemIndex) => itemIndex !== index) })}>Remove</button>}</div>)}</div><Button type="button" variant="ghost" onClick={() => setForm({ ...form, items: [...form.items, { product: '', quantity: '1', unit_cost: '0.00' }] })}>+ Add another product</Button><footer><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create order'}</Button></footer></form></section></div>;
}

function SummaryCard({ icon, label, value }) { return <article className="inventory-summary-card"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></article>; }
