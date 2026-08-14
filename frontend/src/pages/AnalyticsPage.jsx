import { FiActivity, FiAlertTriangle, FiBarChart2, FiDollarSign, FiPackage, FiRepeat, FiShoppingBag, FiTrendingUp, FiUserPlus, FiUsers } from 'react-icons/fi';
import { Link, Navigate } from 'react-router-dom';
import { OrderStatusChart, SalesTrendChart, TopProductsChart } from '../components/AnalyticsCharts';
import { Alert, EmptyState, Loader } from '../components/ui';
import { useAnalyticsStream } from '../hooks/useAnalyticsStream';
import { useAuth } from '../hooks/useAuth';
import { formatPrice } from '../utils/format';

const STATUS_LABELS = {
    pending: 'Pending',
    processing: 'Processing',
    shipped: 'Shipped',
    delivered: 'Delivered',
    cancelled: 'Cancelled',
};

export function AnalyticsPage() {
    const { user } = useAuth();
    const { analytics, loading, error, connection, lastUpdated } = useAnalyticsStream(Boolean(user?.can_manage_orders));
    if (!user?.can_manage_orders)
        return <Navigate to="/account" replace/>;
    if (loading)
        return <div className="container page"><Loader label="Loading store analytics"/></div>;
    if (error && !analytics)
        return <div className="container page"><Alert>{error}</Alert></div>;
    if (!analytics)
        return null;
    const { summary } = analytics;
    const donutColors = { pending: '#f4bf32', processing: '#3568e8', shipped: '#805ad5', delivered: '#23b783', cancelled: '#dc4c3f' };
    const connectionLabel = { live: 'Live stream', connecting: 'Connecting', reconnecting: 'Reconnecting', fallback: 'REST fallback' }[connection];
    return <div className="analytics-shell"><div className="container page analytics-page">
      <div className="page-heading analytics-heading"><div><p className="eyebrow">Staff workspace</p><h1>Store intelligence</h1><p>Live revenue, order activity, product performance, and inventory health.</p><div className={`analytics-live analytics-live--${connection}`} role="status"><span/><strong>{connectionLabel}</strong>{lastUpdated && <time dateTime={lastUpdated.toISOString()}>Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>}</div></div></div>
      {error && <Alert>Live refresh failed: {error}. The most recent data is still displayed.</Alert>}
      <section className="analytics-summary" aria-label="Store summary">
        <MetricCard icon={<FiDollarSign/>} label="Total revenue" value={formatPrice(summary.total_revenue)} note="Paid orders only"/>
        <MetricCard icon={<FiShoppingBag/>} label="Paid orders" value={summary.paid_orders} note={`${summary.total_orders} total orders`}/>
        <MetricCard icon={<FiUsers/>} label="Customers" value={summary.customers} note="Registered customer accounts"/>
        <MetricCard icon={<FiBarChart2/>} label="Average paid order" value={formatPrice(summary.paid_orders ? Number(summary.total_revenue) / summary.paid_orders : 0)} note="Revenue per paid order"/>
      </section>
      <section className="analytics-statistics" aria-labelledby="statistics-heading">
        <header><div><p className="eyebrow">Period comparison</p><h2 id="statistics-heading">Last 30 days</h2></div><p>Compared with the preceding 30-day period.</p></header>
        <div className="analytics-statistics__grid">
          <StatisticCard icon={<FiTrendingUp/>} label="Revenue" value={formatPrice(analytics.statistics.revenue)} change={analytics.statistics.revenue_change_percent}/>
          <StatisticCard icon={<FiActivity/>} label="Paid orders" value={analytics.statistics.paid_orders} change={analytics.statistics.paid_orders_change_percent}/>
          <StatisticCard icon={<FiDollarSign/>} label="Average order value" value={formatPrice(analytics.statistics.average_order_value)} note="Paid orders"/>
          <StatisticCard icon={<FiPackage/>} label="Units sold" value={analytics.statistics.units_sold} note="Across paid orders"/>
          <StatisticCard icon={<FiUsers/>} label="Unique buyers" value={analytics.statistics.unique_customers} note="Customers with paid orders"/>
          <StatisticCard icon={<FiRepeat/>} label="Repeat-buyer rate" value={`${analytics.statistics.repeat_customer_rate}%`} note="Two or more paid orders"/>
          <StatisticCard icon={<FiUserPlus/>} label="New customers" value={analytics.statistics.new_customers} note="Registered in this period"/>
        </div>
      </section>
      <div className="commerce-insights-grid">
        <section className="commerce-insight-card" aria-labelledby="financial-heading">
          <header><div><p className="eyebrow">Money movement</p><h2 id="financial-heading">Revenue composition</h2></div></header>
          <dl className="financial-breakdown">
            <FinancialRow label="Gross merchandise sales" value={analytics.financials.gross_sales}/>
            <FinancialRow label="Discounts" value={analytics.financials.discounts} negative/>
            <FinancialRow label="Shipping collected" value={analytics.financials.shipping}/>
            <FinancialRow label="Tax collected" value={analytics.financials.tax}/>
            <FinancialRow label="Refunds" value={analytics.financials.refunds} negative/>
            <FinancialRow label="Net revenue" value={analytics.financials.net_revenue} total/>
          </dl>
        </section>
        <section className="commerce-insight-card" aria-labelledby="checkout-health-heading">
          <header><div><p className="eyebrow">Payment funnel</p><h2 id="checkout-health-heading">Checkout health</h2></div><strong className="completion-rate">{analytics.checkout_performance.completion_rate}%</strong></header>
          <div className="checkout-funnel" aria-label="Checkout completion funnel">
            <FunnelStep label="Checkouts started" value={analytics.checkout_performance.started} width="100%"/>
            <FunnelStep label="Paid or fulfilled" value={analytics.checkout_performance.completed} width={`${analytics.checkout_performance.completion_rate}%`}/>
            <FunnelStep label="Incomplete" value={analytics.checkout_performance.abandoned_or_failed} width={`${100 - Number(analytics.checkout_performance.completion_rate)}%`} muted/>
          </div>
          <p className="commerce-insight-note">Completion uses recorded checkout attempts; it is not a website-session conversion rate.</p>
        </section>
        <section className="commerce-insight-card" aria-labelledby="inventory-health-heading">
          <header><div><p className="eyebrow">Stock position</p><h2 id="inventory-health-heading">Inventory health</h2></div></header>
          <div className="inventory-health-grid">
            <InsightValue label="Retail stock value" value={formatPrice(analytics.inventory_health.retail_value)}/>
            <InsightValue label="Units available" value={analytics.inventory_health.units_available}/>
            <InsightValue label="Active products" value={analytics.inventory_health.active_products}/>
            <InsightValue label="Low stock" value={analytics.inventory_health.low_stock} warning/>
            <InsightValue label="Out of stock" value={analytics.inventory_health.out_of_stock} danger/>
          </div>
        </section>
      </div>
      <div className="analytics-grid">
        <section className="analytics-panel analytics-panel--wide" aria-labelledby="sales-trend-heading">
          <header><div><p className="eyebrow">Last 30 days</p><h2 id="sales-trend-heading">Daily sales trend</h2></div></header>
          <SalesTrendChart sales={analytics.daily_sales}/>
        </section>
        <section className="analytics-panel" aria-labelledby="status-heading">
          <header><div><p className="eyebrow">Fulfillment</p><h2 id="status-heading">Orders by status</h2></div></header>
          <OrderStatusChart statuses={analytics.orders_by_status} labels={STATUS_LABELS} colors={donutColors} total={summary.total_orders}/>
          <div className="status-breakdown">
            {analytics.orders_by_status.map((item) => <div key={item.status}>
              <div><span>{STATUS_LABELS[item.status] || item.status}</span><strong>{item.count}</strong></div>
              <span className="status-breakdown__track"><span className={`status-breakdown__fill status-breakdown__fill--${item.status}`} style={{ width: `${summary.total_orders ? (item.count / summary.total_orders) * 100 : 0}%` }}/></span>
            </div>)}
          </div>
        </section>
        <section className="analytics-panel" aria-labelledby="top-products-heading">
          <header><div><p className="eyebrow">Paid orders</p><h2 id="top-products-heading">Top-selling products</h2></div></header>
          {analytics.top_products.length ? <TopProductsChart products={analytics.top_products}/> : <EmptyState title="No paid sales yet">Product rankings appear after the first paid order.</EmptyState>}
        </section>
        <section className="analytics-panel" aria-labelledby="category-sales-heading">
          <header><div><p className="eyebrow">Merchandising</p><h2 id="category-sales-heading">Sales by category</h2></div></header>
          {analytics.sales_by_category.length ? <PerformanceBars rows={analytics.sales_by_category} labelKey="category"/> : <EmptyState title="No category sales yet">Category performance appears after paid orders.</EmptyState>}
        </section>
        <section className="analytics-panel analytics-panel--payment" aria-labelledby="payment-mix-heading">
          <header><div><p className="eyebrow">Tender</p><h2 id="payment-mix-heading">Payment mix</h2></div></header>
          {analytics.sales_by_payment_method.length ? <div className="payment-mix">{analytics.sales_by_payment_method.map((method) => <div key={method.payment_method}><span>{humanize(method.payment_method)}</span><strong>{method.orders} orders</strong><small>{formatPrice(method.revenue)}</small></div>)}</div> : <EmptyState title="No paid transactions yet">Payment usage appears after paid orders.</EmptyState>}
        </section>
        <section className="analytics-panel analytics-panel--wide" aria-labelledby="low-stock-heading">
          <header><div><p className="eyebrow">Inventory</p><h2 id="low-stock-heading">Low-stock products</h2></div><FiAlertTriangle aria-hidden="true"/></header>
          {analytics.low_stock_products.length ? <div className="analytics-table-wrap"><table className="analytics-table"><thead><tr><th>Product</th><th>Category</th><th>Units left</th><th><span className="sr-only">Action</span></th></tr></thead><tbody>{analytics.low_stock_products.map((product) => <tr key={product.id}><th scope="row">{product.name}</th><td>{product.category}</td><td><span className="low-stock-count">{product.stock_quantity}</span></td><td><Link className="text-link" to={`/products/${product.slug}`}>View</Link></td></tr>)}</tbody></table></div> : <EmptyState title="Inventory looks healthy">No active products have five or fewer units.</EmptyState>}
        </section>
      </div>
    </div></div>;
}

function MetricCard({ icon, label, value, note }) {
    return <article className="metric-card"><span className="metric-card__icon" aria-hidden="true">{icon}</span><div><span>{label}</span><strong>{value}</strong><small>{note}</small></div></article>;
}

function StatisticCard({ icon, label, value, change, note }) {
    const numericChange = change === null ? null : Number(change);
    const changeClass = numericChange === null || numericChange === 0
        ? 'neutral'
        : numericChange > 0 ? 'positive' : 'negative';
    const comparison = numericChange === null
        ? 'New in this period'
        : `${numericChange > 0 ? '+' : ''}${numericChange.toFixed(1)}% vs previous period`;
    return <article className="statistic-card">
      <div className="statistic-card__heading"><span>{label}</span><span aria-hidden="true">{icon}</span></div>
      <strong>{value}</strong>
      <small className={`statistic-card__change statistic-card__change--${changeClass}`}>{change === undefined ? note : comparison}</small>
    </article>;
}

function FinancialRow({ label, value, negative = false, total = false }) {
    return <div className={total ? 'is-total' : ''}><dt>{label}</dt><dd className={negative && Number(value) ? 'is-negative' : ''}>{negative && Number(value) ? '-' : ''}{formatPrice(value)}</dd></div>;
}

function FunnelStep({ label, value, width, muted = false }) {
    return <div><div><span>{label}</span><strong>{value}</strong></div><span className="checkout-funnel__track"><span className={muted ? 'is-muted' : ''} style={{ width }}/></span></div>;
}

function InsightValue({ label, value, warning = false, danger = false }) {
    const tone = danger ? 'danger' : warning ? 'warning' : 'default';
    return <div className={`insight-value insight-value--${tone}`}><strong>{value}</strong><span>{label}</span></div>;
}

function PerformanceBars({ rows, labelKey }) {
    const maximum = Math.max(...rows.map((row) => Number(row.revenue)), 1);
    return <div className="performance-bars">{rows.map((row) => <div key={row[labelKey]}><div><span>{row[labelKey]}</span><strong>{formatPrice(row.revenue)}</strong></div><span className="performance-bars__track"><span style={{ width: `${Number(row.revenue) / maximum * 100}%` }}/></span><small>{row.units} units sold</small></div>)}</div>;
}

function humanize(value) {
    return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
