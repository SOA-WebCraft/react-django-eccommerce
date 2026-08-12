import { useEffect, useRef, useState } from 'react';
import { FiEdit2, FiPackage, FiPlus, FiSearch, FiTrash2 } from 'react-icons/fi';
import { toast } from 'react-toastify';
import { Navigate, useSearchParams } from 'react-router-dom';
import { ApiError, fieldErrors } from '../api/client';
import { catalogApi } from '../api/services';
import { Alert, Button, EmptyState, Field, Loader, Pagination } from '../components/ui';
import { useAuth } from '../hooks/useAuth';
import { formatPrice } from '../utils/format';

const emptyProduct = {
    name: '', slug: '', description: '', price: '', stock_quantity: '0',
    category: '', is_active: true, image: null,
};

const slugify = (value) => value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

export function ProductManagementPage() {
    const { user } = useAuth();
    const [params, setParams] = useSearchParams();
    const page = Number(params.get('page') || 1);
    const [products, setProducts] = useState([]);
    const [categories, setCategories] = useState([]);
    const [count, setCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [search, setSearch] = useState(params.get('search') || '');
    const [editor, setEditor] = useState(null);
    const [deleting, setDeleting] = useState(null);
    const [saving, setSaving] = useState(false);
    const loadProducts = async () => {
        setLoading(true);
        setError('');
        try {
            const data = await catalogApi.products({
                page,
                search: params.get('search') || undefined,
                is_active: params.get('is_active') || undefined,
                ordering: '-created_at',
            });
            setProducts(data.results);
            setCount(data.count);
        }
        catch (reason) { setError(reason.message); }
        finally { setLoading(false); }
    };
    useEffect(() => {
        if (user?.can_manage_catalog)
            void loadProducts();
        // Search parameters are the source of truth for this server query.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user, params, page]);
    useEffect(() => {
        catalogApi.categories().then((data) => setCategories(data.results)).catch(() => undefined);
    }, []);
    if (!user?.can_manage_catalog)
        return <Navigate to="/account" replace/>;
    const updateQuery = (values) => {
        const next = new URLSearchParams(params);
        Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
        if (!('page' in values)) next.delete('page');
        setParams(next);
    };
    const openCreate = () => setEditor({ product: null, form: { ...emptyProduct, category: String(categories[0]?.id || '') }, errors: {} });
    const openEdit = (product) => setEditor({
        product,
        form: {
            name: product.name,
            slug: product.slug,
            description: product.description,
            price: product.price,
            stock_quantity: String(product.stock_quantity),
            category: String(product.category),
            is_active: product.is_active,
            image: null,
        },
        errors: {},
    });
    const saveProduct = async (event) => {
        event.preventDefault();
        const validation = {};
        if (!editor.form.name.trim()) validation.name = 'Enter a product name.';
        if (!editor.form.slug.trim()) validation.slug = 'Enter a product slug.';
        if (!editor.form.category) validation.category = 'Choose a category.';
        if (Number(editor.form.price) < 0 || editor.form.price === '') validation.price = 'Enter a price of zero or greater.';
        if (!Number.isInteger(Number(editor.form.stock_quantity)) || Number(editor.form.stock_quantity) < 0) validation.stock_quantity = 'Enter a whole stock quantity of zero or greater.';
        if (Object.keys(validation).length) {
            setEditor((current) => ({ ...current, errors: validation }));
            return;
        }
        const body = new FormData();
        ['name', 'slug', 'description', 'price', 'stock_quantity', 'category'].forEach((field) => body.append(field, editor.form[field]));
        body.append('is_active', String(editor.form.is_active));
        if (editor.form.image) body.append('image', editor.form.image);
        setSaving(true);
        try {
            if (editor.product)
                await catalogApi.updateProduct(editor.product.slug, body);
            else
                await catalogApi.createProduct(body);
            toast.success(editor.product ? 'Product updated successfully.' : 'Product created successfully.');
            setEditor(null);
            await loadProducts();
        }
        catch (reason) {
            setEditor((current) => ({ ...current, errors: reason instanceof ApiError ? fieldErrors(reason.data) : { detail: 'Unable to save product.' } }));
        }
        finally { setSaving(false); }
    };
    const deleteProduct = async () => {
        setSaving(true);
        try {
            await catalogApi.deleteProduct(deleting.slug);
            toast.success(`${deleting.name} deleted.`);
            setDeleting(null);
            await loadProducts();
        }
        catch (reason) {
            if (!(reason instanceof ApiError)) toast.error(reason.message || 'Unable to delete product.');
        }
        finally { setSaving(false); }
    };
    return <div className="staff-catalog-shell"><div className="container page staff-catalog-page">
      <div className="page-heading staff-catalog-heading"><div><p className="eyebrow">Staff workspace</p><h1>Product management</h1><p>Create products, adjust inventory, update catalog details, and control storefront visibility.</p></div><Button onClick={openCreate}><FiPlus aria-hidden="true"/> Add product</Button></div>
      <div className="staff-catalog-toolbar">
        <form role="search" onSubmit={(event) => { event.preventDefault(); updateQuery({ search: search.trim() }); }}><FiSearch aria-hidden="true"/><input aria-label="Search products" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search catalog"/><button type="submit">Search</button></form>
        <label>Status<select value={params.get('is_active') || ''} onChange={(event) => updateQuery({ is_active: event.target.value })}><option value="">All products</option><option value="true">Active</option><option value="false">Inactive</option></select></label>
      </div>
      {error ? <Alert>{error}</Alert> : loading ? <Loader label="Loading catalog"/> : products.length ? <div className="staff-product-table-wrap"><table className="staff-product-table"><thead><tr><th>Product</th><th>Category</th><th>Price</th><th>Stock</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{products.map((product) => <tr key={product.id}><th scope="row"><div className="staff-product-identity">{product.image ? <img src={product.image} alt=""/> : <span><FiPackage/></span>}<div><strong>{product.name}</strong><small>{product.slug}</small></div></div></th><td>{product.category_name}</td><td>{formatPrice(product.price)}</td><td><span className={product.stock_quantity <= 5 ? 'inventory-low' : ''}>{product.stock_quantity}</span></td><td><span className={`catalog-state catalog-state--${product.is_active ? 'active' : 'inactive'}`}>{product.is_active ? 'Active' : 'Inactive'}</span></td><td><div className="staff-product-actions"><button type="button" aria-label={`Edit ${product.name}`} onClick={() => openEdit(product)}><FiEdit2/></button><button type="button" className="is-danger" aria-label={`Delete ${product.name}`} onClick={() => setDeleting(product)}><FiTrash2/></button></div></td></tr>)}</tbody></table></div> : <EmptyState title="No matching products" action={<Button onClick={openCreate}>Add your first product</Button>}>Create a product or adjust your search and status filter.</EmptyState>}
      <Pagination page={page} count={count} onPage={(next) => updateQuery({ page: String(next) })}/>
      {editor && <ProductEditor editor={editor} setEditor={setEditor} categories={categories} saving={saving} onSave={saveProduct} onClose={() => setEditor(null)}/>} 
      {deleting && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) setDeleting(null); }}><section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-product-title"><p className="eyebrow">Delete product</p><h2 id="delete-product-title">Delete {deleting.name}?</h2><p>This removes the product and its uploaded images. Historical order-item snapshots remain unchanged.</p><div className="confirm-modal__actions"><Button variant="secondary" disabled={saving} onClick={() => setDeleting(null)}>Cancel</Button><Button variant="danger" disabled={saving} onClick={() => void deleteProduct()}>{saving ? 'Deleting…' : 'Delete product'}</Button></div></section></div>}
    </div></div>;
}

function ProductEditor({ editor, setEditor, categories, saving, onSave, onClose }) {
    const nameInput = useRef(null);
    useEffect(() => { nameInput.current?.focus(); }, []);
    const change = (field) => (event) => {
        const value = field === 'is_active' ? event.target.checked : field === 'image' ? event.target.files[0] || null : event.target.value;
        setEditor((current) => ({ ...current, form: { ...current.form, [field]: value }, errors: { ...current.errors, [field]: '' } }));
    };
    const changeName = (event) => {
        const value = event.target.value;
        setEditor((current) => ({ ...current, form: { ...current.form, name: value, slug: current.product ? current.form.slug : slugify(value) }, errors: { ...current.errors, name: '', slug: '' } }));
    };
    return <div className="modal-backdrop product-editor-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) onClose(); }}><section className="product-editor-modal" role="dialog" aria-modal="true" aria-labelledby="product-editor-title"><header><div><p className="eyebrow">Catalog editor</p><h2 id="product-editor-title">{editor.product ? 'Update product' : 'Add product'}</h2></div><button type="button" aria-label="Close product editor" disabled={saving} onClick={onClose}>×</button></header><form onSubmit={onSave}>{editor.errors.detail && <Alert>{editor.errors.detail}</Alert>}<div className="product-editor-grid"><Field ref={nameInput} label="Product name" name="product-name" required value={editor.form.name} error={editor.errors.name} onChange={changeName}/><Field label="Slug" name="product-slug" required value={editor.form.slug} error={editor.errors.slug} onChange={change('slug')}/><label className="field"><span>Category</span><select required value={editor.form.category} aria-invalid={Boolean(editor.errors.category)} onChange={change('category')}><option value="">Choose category</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select>{editor.errors.category && <small className="field__error">{editor.errors.category}</small>}</label><Field label="Price" name="product-price" type="number" min="0" step="0.01" required value={editor.form.price} error={editor.errors.price} onChange={change('price')}/><Field label="Stock quantity" name="product-stock" type="number" min="0" step="1" required value={editor.form.stock_quantity} error={editor.errors.stock_quantity} onChange={change('stock_quantity')}/><label className="field"><span>Primary image</span><input type="file" accept="image/jpeg,image/png,image/webp" onChange={change('image')}/><small>JPEG, PNG, or WebP up to 5 MB.</small>{editor.errors.image && <small className="field__error">{editor.errors.image}</small>}</label><label className="field product-description-field"><span>Description</span><textarea rows="7" value={editor.form.description} onChange={change('description')}/>{editor.errors.description && <small className="field__error">{editor.errors.description}</small>}</label><label className="catalog-active-toggle"><input type="checkbox" checked={editor.form.is_active} onChange={change('is_active')}/><span><strong>Active product</strong><small>Visible to customers in the storefront.</small></span></label></div><footer><Button type="button" variant="secondary" disabled={saving} onClick={onClose}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Saving…' : editor.product ? 'Save changes' : 'Create product'}</Button></footer></form></section></div>;
}
