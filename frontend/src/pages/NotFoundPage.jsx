import { Link } from 'react-router-dom';
export function NotFoundPage() {
    return <div className="container not-found"><p className="not-found__code">404</p><p className="eyebrow">Lost in the signal</p><h1>This page isn’t connected.</h1><p>The address may have changed, or the page no longer exists.</p><Link className="button button--primary" to="/">Return home</Link></div>;
}
