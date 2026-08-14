import { useEffect, useRef, useState } from 'react';
import { FiChevronDown, FiGrid, FiLogOut, FiShoppingCart, FiUser } from 'react-icons/fi';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { catalogApi } from '../api/services';
import { useAuth } from '../hooks/useAuth';
import { useCart } from '../hooks/useCart';
import { useToast } from '../hooks/useToast';
export function StoreLayout() {
    const [categories, setCategories] = useState([]);
    const [menuOpen, setMenuOpen] = useState(false);
    const [accountMenuOpen, setAccountMenuOpen] = useState(false);
    const [search, setSearch] = useState('');
    const accountMenuRef = useRef(null);
    const { user, isAuthenticated, logout } = useAuth();
    const { count, clearLocal } = useCart();
    const { notify } = useToast();
    const navigate = useNavigate();
    const location = useLocation();
    useEffect(() => {
        catalogApi.categories().then((data) => setCategories(data.results)).catch(() => undefined);
    }, []);
    useEffect(() => {
        setAccountMenuOpen(false);
    }, [location.pathname]);
    useEffect(() => {
        const closeAccountMenu = (event) => {
            if (accountMenuRef.current && !accountMenuRef.current.contains(event.target)) {
                setAccountMenuOpen(false);
            }
        };
        const closeAccountMenuWithKeyboard = (event) => {
            if (event.key === 'Escape') {
                setAccountMenuOpen(false);
            }
        };
        document.addEventListener('pointerdown', closeAccountMenu);
        document.addEventListener('keydown', closeAccountMenuWithKeyboard);
        return () => {
            document.removeEventListener('pointerdown', closeAccountMenu);
            document.removeEventListener('keydown', closeAccountMenuWithKeyboard);
        };
    }, []);
    const submitSearch = (event) => {
        event.preventDefault();
        const value = search.trim();
        navigate(value ? `/products?search=${encodeURIComponent(value)}` : '/products');
        setMenuOpen(false);
    };
    return (<>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <div className="announcement">Complimentary delivery on orders over $100</div>
      <header className="site-header">
        <div className="header-main container">
          <button className="icon-button mobile-only" aria-label="Toggle navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>☰</button>
          <Link className="brand" to="/" aria-label="ECCO home">
            EC<span>CO</span>
          </Link>
          <form className="header-search" role="search" onSubmit={submitSearch}>
            <label className="sr-only" htmlFor="site-search">Search products</label>
            <input id="site-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search phones, laptops, accessories…"/>
            <button type="submit" aria-label="Search">⌕</button>
          </form>
          <nav className="header-actions" aria-label="Customer navigation">
            {isAuthenticated ? (<div className="user-menu" ref={accountMenuRef}>
                <button
                  className="account-menu__trigger"
                  type="button"
                  aria-haspopup="menu"
                  aria-expanded={accountMenuOpen}
                  aria-controls="account-menu"
                  onClick={() => setAccountMenuOpen((open) => !open)}
                >
                  <FiUser aria-hidden="true" />
                  <span>Account</span>
                  <FiChevronDown className={accountMenuOpen ? 'is-open' : ''} aria-hidden="true" />
                </button>
                {accountMenuOpen && <div id="account-menu" className="account-menu" role="menu">
                  <div className="account-menu__identity">
                    <span>Signed in as</span>
                    <strong>{user?.username}</strong>
                  </div>
                  <NavLink to="/account" role="menuitem">
                    <FiUser aria-hidden="true" /> Profile
                  </NavLink>
                  {(user?.can_manage_orders || user?.can_manage_catalog || user?.can_manage_settings) && <NavLink to={user?.can_manage_orders || user?.can_manage_catalog ? '/staff/dashboard' : '/staff/settings'} role="menuitem">
                    <FiGrid aria-hidden="true" /> Dashboard
                  </NavLink>}
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                        setAccountMenuOpen(false);
                        void logout().catch(() => undefined).finally(() => {
                            clearLocal();
                            notify('You have been logged out.', 'success');
                            navigate('/');
                        });
                    }}
                  >
                    <FiLogOut aria-hidden="true" /> Logout
                  </button>
                </div>}
              </div>) : (<NavLink to="/login">Sign in</NavLink>)}
            <NavLink to="/cart" className="cart-link" aria-label={`Cart with ${count} items`}>
              <FiShoppingCart className="cart-link__icon" aria-hidden="true"/>
              <span className="cart-link__count" aria-hidden="true">{count}</span>
            </NavLink>
          </nav>
        </div>
        <nav className={`category-nav ${menuOpen ? 'category-nav--open' : ''}`} aria-label="Product categories">
          <div className="container">
            <NavLink to="/products" onClick={() => setMenuOpen(false)}>Shop all</NavLink>
            {categories.map((category) => (<NavLink key={category.id} to={`/products?category=${category.slug}`} onClick={() => setMenuOpen(false)}>
                {category.name}
              </NavLink>))}
          </div>
        </nav>
      </header>
      <main id="main-content"><Outlet /></main>
      <footer className="site-footer">
        <div className="container footer-grid">
          <div>
            <Link className="brand brand--light" to="/">ECCO</Link>
            <p>Technology selected for the way you live, work, and create.</p>
          </div>
          <div><h2>Shop</h2><Link to="/products">All products</Link><Link to="/products?ordering=-created_at">New arrivals</Link></div>
          <div><h2>Account</h2><Link to="/account">Profile</Link><Link to={user?.can_manage_orders ? '/staff/orders' : '/account/orders'}>{user?.can_manage_orders ? 'Manage orders' : 'Orders'}</Link>{user?.can_manage_orders && <Link to="/staff/analytics">Analytics</Link>}{user?.can_manage_catalog && <Link to="/staff/products">Manage products</Link>}</div>
          <div><h2>Need help?</h2><p>Browse the catalog or sign in to manage your orders.</p></div>
        </div>
        <div className="container footer-bottom">© {new Date().getFullYear()} ECCO. Demo storefront.</div>
      </footer>
    </>);
}
