export function Button({ children, variant = 'primary', className = '', ...props }) {
    return (<button className={`button button--${variant} ${className}`} {...props}>
      {children}
    </button>);
}
export function Field({ label, error, hint, ...props }) {
    const id = props.id || props.name;
    return (<label className="field" htmlFor={id}>
      <span>{label}</span>
      <input id={id} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} {...props}/>
      {hint && <small>{hint}</small>}
      {error && (<small id={`${id}-error`} className="field__error">
          {error}
        </small>)}
    </label>);
}
export function Loader({ label = 'Loading' }) {
    return (<div className="loader" role="status">
      <span className="spinner" aria-hidden="true"/>
      <span>{label}</span>
    </div>);
}
export function Alert({ children, kind = 'error', }) {
    return (<div className={`alert alert--${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </div>);
}
export function EmptyState({ title, children, action, }) {
    return (<div className="empty-state">
      <div className="empty-state__icon" aria-hidden="true">◇</div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>);
}
export function QuantityControl({ value, min = 1, max, onDecrease, onIncrease, disabled, }) {
    return (<div className="quantity" aria-label="Quantity selector">
      <button type="button" aria-label="Decrease quantity" disabled={disabled || value <= min} onClick={onDecrease}>−</button>
      <span aria-live="polite">{value}</span>
      <button type="button" aria-label="Increase quantity" disabled={disabled || value >= max} onClick={onIncrease}>+</button>
    </div>);
}
export function Pagination({ page, count, pageSize = 20, onPage, }) {
    const pages = Math.ceil(count / pageSize);
    if (pages <= 1)
        return null;
    return (<nav className="pagination" aria-label="Pagination">
      <Button variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span>Page {page} of {pages}</span>
      <Button variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </nav>);
}
