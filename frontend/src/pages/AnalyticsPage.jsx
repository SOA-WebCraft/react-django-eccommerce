import { useCallback, useEffect, useRef, useState } from 'react';
import { FiAlertTriangle, FiBarChart2, FiDollarSign, FiShoppingBag, FiUsers } from 'react-icons/fi';
import { Link, Navigate } from 'react-router-dom';
import { analyticsApi } from '../api/services';
import { Alert, EmptyState, Loader } from '../components/ui';
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
    const [analytics, setAnalytics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');
    const [lastUpdated, setLastUpdated] = useState(null);
    const requestRunning = useRef(false);
    const loadAnalytics = useCallback(async ({ initial = false } = {}) => {
        if (!user?.can_manage_orders || requestRunning.current)
            return;
        requestRunning.current = true;
        if (!initial)
            setRefreshing(true);
        try {
            const data = await analyticsApi.get();
            setAnalytics(data);
            setLastUpdated(new Date());
            setError('');
        }
        catch (reason) {
            setError(reason.message);
        }
        finally {
            requestRunning.current = false;
            setLoading(false);
            setRefreshing(false);
        }
    }, [user]);
    useEffect(() => {
        if (!user?.can_manage_orders)
            return;
        void loadAnalytics({ initial: true });
        const interval = window.setInterval(() => {
            if (!document.hidden)
                void loadAnalytics();
        }, 10000);
        const refreshVisiblePage = () => {
            if (!document.hidden)
                void loadAnalytics();
        };
        document.addEventListener('visibilitychange', refreshVisiblePage);
        window.addEventListener('focus', refreshVisiblePage);
        return () => {
            window.clearInterval(interval);
            document.removeEventListener('visibilitychange', refreshVisiblePage);
            window.removeEventListener('focus', refreshVisiblePage);
        };
    }, [loadAnalytics, user]);
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
    let statusStart = 0;
    const statusSegments = analytics.orders_by_status.map((item) => {
        const statusEnd = statusStart + (summary.total_orders ? item.count / summary.total_orders * 100 : 0);
        const segment = `${donutColors[item.status] || '#94a3b8'} ${statusStart}% ${statusEnd}%`;
        statusStart = statusEnd;
        return segment;
    });
    const statusDonut = { background: summary.total_orders ? `conic-gradient(${statusSegments.join(', ')})` : '#edf1f5' };
    return <div className="analytics-shell"><div className="container page analytics-page">
      <div className="page-heading analytics-heading"><div><p className="eyebrow">Staff workspace</p><h1>Store analytics</h1><p>Paid revenue, order activity, product performance, and inventory health.</p><div className="analytics-live" role="status"><span className={refreshing ? 'is-refreshing' : ''}/><strong>{refreshing ? 'Updating' : 'Live'}</strong>{lastUpdated && <time dateTime={lastUpdated.toISOString()}>Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>}</div></div></div>
      {error && <Alert>Live refresh failed: {error}. The most recent data is still displayed.</Alert>}
      <section className="analytics-summary" aria-label="Store summary">
        <MetricCard icon={<FiDollarSign/>} label="Total revenue" value={formatPrice(summary.total_revenue)} note="Paid orders only"/>
        <MetricCard icon={<FiShoppingBag/>} label="Paid orders" value={summary.paid_orders} note={`${summary.total_orders} total orders`}/>
        <MetricCard icon={<FiUsers/>} label="Customers" value={summary.customers} note="Registered customer accounts"/>
        <MetricCard icon={<FiBarChart2/>} label="Average paid order" value={formatPrice(summary.paid_orders ? Number(summary.total_revenue) / summary.paid_orders : 0)} note="Revenue per paid order"/>
      </section>
      <div className="analytics-grid">
        <section className="analytics-panel analytics-panel--wide" aria-labelledby="sales-trend-heading">
          <header><div><p className="eyebrow">Last 30 days</p><h2 id="sales-trend-heading">Daily sales trend</h2></div></header>
          <DailySalesChart sales={analytics.daily_sales}/>
        </section>
        <section className="analytics-panel" aria-labelledby="status-heading">
          <header><div><p className="eyebrow">Fulfillment</p><h2 id="status-heading">Orders by status</h2></div></header>
          <div className="status-donut" style={statusDonut}><span><strong>{summary.total_orders}</strong>Total</span></div>
          <div className="status-breakdown">
            {analytics.orders_by_status.map((item) => <div key={item.status}>
              <div><span>{STATUS_LABELS[item.status] || item.status}</span><strong>{item.count}</strong></div>
              <span className="status-breakdown__track"><span className={`status-breakdown__fill status-breakdown__fill--${item.status}`} style={{ width: `${summary.total_orders ? (item.count / summary.total_orders) * 100 : 0}%` }}/></span>
            </div>)}
          </div>
        </section>
        <section className="analytics-panel" aria-labelledby="top-products-heading">
          <header><div><p className="eyebrow">Paid orders</p><h2 id="top-products-heading">Top-selling products</h2></div></header>
          {analytics.top_products.length ? <ol className="top-products">{analytics.top_products.map((product, index) => <li key={`${product.product_id}-${product.product_name}`}><span className="top-products__rank">{index + 1}</span><div><strong>{product.product_name}</strong><span>{product.quantity_sold} sold</span></div><strong>{formatPrice(product.revenue)}</strong></li>)}</ol> : <EmptyState title="No paid sales yet">Product rankings appear after the first paid order.</EmptyState>}
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

function DailySalesChart({ sales }) {
    const width = 820;
    const height = 280;
    const plot = { left: 78, right: 18, top: 16, bottom: 42 };
    const plotWidth = width - plot.left - plot.right;
    const plotHeight = height - plot.top - plot.bottom;
    const maxRevenue = Math.max(1, ...sales.map((day) => Number(day.revenue)));
    const points = sales.map((day, index) => ({
        ...day,
        x: plot.left + (sales.length > 1 ? index / (sales.length - 1) * plotWidth : plotWidth / 2),
        y: plot.top + plotHeight - Number(day.revenue) / maxRevenue * plotHeight,
    }));
    const linePoints = points.map((point) => `${point.x},${point.y}`).join(' ');
    const areaPoints = points.length
        ? `${plot.left},${plot.top + plotHeight} ${linePoints} ${plot.left + plotWidth},${plot.top + plotHeight}`
        : '';
    const ticks = [1, .75, .5, .25, 0];
    const dateIndexes = [...new Set([0, Math.floor((sales.length - 1) / 2), sales.length - 1])].filter((index) => index >= 0 && index < sales.length);
    const formatDateLabel = (value) => new Date(`${value}T00:00:00`).toLocaleDateString([], { month: 'short', day: 'numeric' });

    return <div className="sales-trend-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="daily-sales-chart-title daily-sales-chart-description">
        <title id="daily-sales-chart-title">Daily paid revenue for the last 30 days</title>
        <desc id="daily-sales-chart-description">A line chart showing changes in daily paid revenue.</desc>
        <defs>
          <linearGradient id="sales-area-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#386ce8" stopOpacity=".28"/>
            <stop offset="100%" stopColor="#386ce8" stopOpacity=".02"/>
          </linearGradient>
        </defs>
        {ticks.map((tick) => {
            const y = plot.top + (1 - tick) * plotHeight;
            return <g key={tick} className="sales-trend-chart__grid">
              <line x1={plot.left} x2={plot.left + plotWidth} y1={y} y2={y}/>
              <text x={plot.left - 12} y={y + 4}>{formatPrice(maxRevenue * tick)}</text>
            </g>;
        })}
        {areaPoints && <polygon className="sales-trend-chart__area" points={areaPoints}/>}
        {linePoints && <polyline className="sales-trend-chart__line" points={linePoints}/>}
        {points.map((point) => <circle className="sales-trend-chart__point" key={point.date} cx={point.x} cy={point.y} r="4" tabIndex="0">
          <title>{point.date}: {formatPrice(point.revenue)} from {point.orders} paid {point.orders === 1 ? 'order' : 'orders'}</title>
        </circle>)}
        {dateIndexes.map((index) => <text className="sales-trend-chart__date" key={sales[index].date} x={points[index].x} y={height - 12} textAnchor={index === 0 ? 'start' : index === sales.length - 1 ? 'end' : 'middle'}>{formatDateLabel(sales[index].date)}</text>)}
      </svg>
      <ol className="sr-only">{sales.map((day) => <li key={day.date}>{day.date}: {formatPrice(day.revenue)}, {day.orders} paid orders</li>)}</ol>
    </div>;
}
