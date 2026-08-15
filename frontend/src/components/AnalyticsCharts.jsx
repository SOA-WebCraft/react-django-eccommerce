import { useEffect, useRef } from 'react';
import {
    ArcElement,
    BarController,
    BarElement,
    CategoryScale,
    Chart,
    DoughnutController,
    Filler,
    Legend,
    LinearScale,
    LineController,
    LineElement,
    PointElement,
    Tooltip,
} from 'chart.js';
import { formatPrice } from '../utils/format';

Chart.register(
    ArcElement,
    BarController,
    BarElement,
    CategoryScale,
    DoughnutController,
    Filler,
    Legend,
    LinearScale,
    LineController,
    LineElement,
    PointElement,
    Tooltip,
);

function useChart(createConfig, values) {
    const canvasRef = useRef(null);
    const chartRef = useRef(null);
    useEffect(() => {
        if (!canvasRef.current)
            return;
        chartRef.current = new Chart(canvasRef.current, createConfig());
        return () => chartRef.current?.destroy();
    }, [createConfig]);
    useEffect(() => {
        if (!chartRef.current)
            return;
        chartRef.current.data.labels = values.labels;
        chartRef.current.data.datasets.forEach((dataset, index) => {
            dataset.data = values.datasets[index];
        });
        chartRef.current.update('none');
    }, [values]);
    return canvasRef;
}

const currencyTick = (value) => formatPrice(value);

export function SalesTrendChart({ sales }) {
    const labels = sales.map((day) => new Date(`${day.date}T00:00:00`).toLocaleDateString([], { month: 'short', day: 'numeric' }));
    const revenue = sales.map((day) => Number(day.revenue));
    const values = { labels, datasets: [revenue] };
    const createConfig = () => ({
        type: 'line',
        data: { labels, datasets: [{
            label: 'Paid revenue', data: revenue, fill: true,
            borderColor: '#0c8a61', backgroundColor: 'rgba(12,138,97,.12)',
            borderWidth: 3, pointRadius: 0, pointHoverRadius: 6,
            pointBackgroundColor: '#fff', pointBorderColor: '#0c8a61',
            pointBorderWidth: 3, tension: .35,
        }] },
        options: {
            responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
            animation: { duration: 550 },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (context) => `Revenue: ${formatPrice(context.parsed.y)}` } },
            },
            scales: {
                x: { grid: { display: false }, ticks: { maxTicksLimit: 6, color: '#718096' }, border: { display: false } },
                y: { beginAtZero: true, grid: { color: '#e8edf4' }, ticks: { color: '#718096', callback: currencyTick }, border: { display: false } },
            },
        },
    });
    const canvasRef = useChart(createConfig, values);
    return <div className="chart-canvas chart-canvas--line"><canvas ref={canvasRef} aria-label="Daily paid revenue line chart" role="img"/></div>;
}

export function OrderStatusChart({ statuses, labels, colors, total }) {
    const chartLabels = statuses.map((item) => labels[item.status] || item.status);
    const counts = statuses.map((item) => item.count);
    const values = { labels: chartLabels, datasets: [counts] };
    const createConfig = () => ({
        type: 'doughnut',
        data: { labels: chartLabels, datasets: [{ data: counts, backgroundColor: statuses.map((item) => colors[item.status]), borderWidth: 0, hoverOffset: 5 }] },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '72%',
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => `${context.label}: ${context.parsed}` } } },
        },
        plugins: [{
            id: 'centerTotal',
            afterDraw(chart) {
                const { ctx, chartArea } = chart;
                if (!chartArea)
                    return;
                ctx.save();
                ctx.textAlign = 'center';
                ctx.fillStyle = '#fff';
                ctx.font = '800 24px Manrope';
                ctx.fillText(String(total), (chartArea.left + chartArea.right) / 2, (chartArea.top + chartArea.bottom) / 2);
                ctx.fillStyle = '#c8d7f0';
                ctx.font = '700 10px DM Sans';
                ctx.fillText('TOTAL ORDERS', (chartArea.left + chartArea.right) / 2, (chartArea.top + chartArea.bottom) / 2 + 18);
                ctx.restore();
            },
        }],
    });
    const canvasRef = useChart(createConfig, values);
    return <div className="chart-canvas chart-canvas--doughnut"><canvas ref={canvasRef} aria-label="Orders grouped by status" role="img"/></div>;
}

export function TopProductsChart({ products }) {
    const labels = products.map((product) => product.product_name);
    const quantities = products.map((product) => product.quantity_sold);
    const values = { labels, datasets: [quantities] };
    const createConfig = () => ({
        type: 'bar',
        data: { labels, datasets: [{ label: 'Units sold', data: quantities, backgroundColor: '#0c8a61', borderRadius: 7, barThickness: 17 }] },
        options: {
            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { afterLabel: (context) => `Revenue: ${formatPrice(products[context.dataIndex].revenue)}` } } },
            scales: {
                x: { beginAtZero: true, ticks: { precision: 0, color: '#718096' }, grid: { color: '#edf1f5' }, border: { display: false } },
                y: { ticks: { color: '#334155' }, grid: { display: false }, border: { display: false } },
            },
        },
    });
    const canvasRef = useChart(createConfig, values);
    return <div className="chart-canvas chart-canvas--products"><canvas ref={canvasRef} aria-label="Top-selling products bar chart" role="img"/></div>;
}
