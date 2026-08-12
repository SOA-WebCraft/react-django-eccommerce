import { useEffect, useState } from 'react';
import { FiArchive, FiBarChart2, FiBox, FiChevronLeft, FiCreditCard, FiGift, FiMenu, FiSettings, FiShoppingBag, FiTruck, FiUsers, FiX } from 'react-icons/fi';
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function StaffDashboardLayout() {
    const { user } = useAuth();
    const location = useLocation();
    const [menuOpen, setMenuOpen] = useState(false);
    const canAccessDashboard = Boolean(user?.can_manage_orders || user?.can_manage_catalog || user?.can_manage_settings);
    useEffect(() => {
        setMenuOpen(false);
    }, [location.pathname]);
    useEffect(() => {
        if (!menuOpen)
            return undefined;
        const closeOnEscape = (event) => {
            if (event.key === 'Escape')
                setMenuOpen(false);
        };
        document.addEventListener('keydown', closeOnEscape);
        return () => document.removeEventListener('keydown', closeOnEscape);
    }, [menuOpen]);
    if (!canAccessDashboard)
        return <Navigate to="/account" replace/>;
    const analyticsActive = location.pathname === '/staff/dashboard' || location.pathname === '/staff/analytics';
    return <div className="staff-dashboard-layout">
      <div className="staff-dashboard-mobile-bar">
        <strong>Dashboard</strong>
        <button type="button" aria-label="Open dashboard navigation" aria-expanded={menuOpen} aria-controls="staff-dashboard-sidebar" onClick={() => setMenuOpen(true)}><FiMenu aria-hidden="true"/></button>
      </div>
      {menuOpen && <button type="button" className="staff-dashboard-backdrop" aria-label="Close dashboard navigation" onClick={() => setMenuOpen(false)}/>} 
      <aside id="staff-dashboard-sidebar" className={`staff-dashboard-sidebar${menuOpen ? ' is-open' : ''}`} aria-label="Staff dashboard navigation">
        <div className="staff-dashboard-sidebar__heading">
          <div><span>ECCO staff</span><strong>Dashboard</strong></div>
          <button type="button" aria-label="Close dashboard navigation" onClick={() => setMenuOpen(false)}><FiX aria-hidden="true"/></button>
        </div>
        <nav>
          {user?.can_manage_orders && <NavLink to="/staff/analytics" className={() => analyticsActive ? 'active' : ''}><FiBarChart2 aria-hidden="true"/><span>Analytics</span></NavLink>}
          {user?.can_manage_orders && <NavLink to="/staff/orders" className={({ isActive }) => isActive ? 'active' : ''}><FiShoppingBag aria-hidden="true"/><span>Orders</span></NavLink>}
          {user?.can_manage_orders && <NavLink to="/staff/payments" className={({ isActive }) => isActive ? 'active' : ''}><FiCreditCard aria-hidden="true"/><span>Payments</span></NavLink>}
          {user?.can_manage_orders && <NavLink to="/staff/shipping" className={({ isActive }) => isActive ? 'active' : ''}><FiTruck aria-hidden="true"/><span>Shipping</span></NavLink>}
          {user?.can_manage_orders && <NavLink to="/staff/discounts" className={({ isActive }) => isActive ? 'active' : ''}><FiGift aria-hidden="true"/><span>Discounts</span></NavLink>}
          {user?.can_manage_orders && <NavLink to="/staff/customers" className={({ isActive }) => isActive ? 'active' : ''}><FiUsers aria-hidden="true"/><span>Customers</span></NavLink>}
          {user?.can_manage_orders && <NavLink to="/staff/inventory" className={({ isActive }) => isActive ? 'active' : ''}><FiArchive aria-hidden="true"/><span>Inventory</span></NavLink>}
          {user?.can_manage_catalog && <NavLink to="/staff/products" className={({ isActive }) => isActive ? 'active' : ''}><FiBox aria-hidden="true"/><span>Products</span></NavLink>}
          {user?.can_manage_settings && <NavLink to="/staff/settings" className={({ isActive }) => isActive ? 'active' : ''}><FiSettings aria-hidden="true"/><span>Settings</span></NavLink>}
        </nav>
        <Link className="staff-dashboard-sidebar__back" to="/account"><FiChevronLeft aria-hidden="true"/> Back to account</Link>
      </aside>
      <section className="staff-dashboard-content" aria-label="Dashboard content"><Outlet/></section>
    </div>;
}
