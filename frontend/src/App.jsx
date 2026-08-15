import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Loader } from './components/ui';
import { StoreLayout } from './layouts/StoreLayout';

const lazyNamed = (loader, name) => lazy(() => loader().then((module) => ({ default: module[name] })));
const StaffDashboardLayout = lazyNamed(() => import('./layouts/StaffDashboardLayout'), 'StaffDashboardLayout');
const LoginPage = lazyNamed(() => import('./pages/AuthPages'), 'LoginPage');
const RegisterPage = lazyNamed(() => import('./pages/AuthPages'), 'RegisterPage');
const ForgotPasswordPage = lazyNamed(() => import('./pages/AuthPages'), 'ForgotPasswordPage');
const ResetPasswordPage = lazyNamed(() => import('./pages/AuthPages'), 'ResetPasswordPage');
const SocialAuthCallbackPage = lazyNamed(() => import('./pages/AuthPages'), 'SocialAuthCallbackPage');
const CartPage = lazyNamed(() => import('./pages/CartPage'), 'CartPage');
const CheckoutPage = lazyNamed(() => import('./pages/CheckoutPages'), 'CheckoutPage');
const ConfirmationPage = lazyNamed(() => import('./pages/CheckoutPages'), 'ConfirmationPage');
const HomePage = lazyNamed(() => import('./pages/HomePage'), 'HomePage');
const NotFoundPage = lazyNamed(() => import('./pages/NotFoundPage'), 'NotFoundPage');
const AccountPage = lazyNamed(() => import('./pages/OrderPages'), 'AccountPage');
const OrderDetailPage = lazyNamed(() => import('./pages/OrderPages'), 'OrderDetailPage');
const OrdersPage = lazyNamed(() => import('./pages/OrderPages'), 'OrdersPage');
const ProductDetailPage = lazyNamed(() => import('./pages/ProductDetailPage'), 'ProductDetailPage');
const ProductListPage = lazyNamed(() => import('./pages/ProductListPage'), 'ProductListPage');
const AnalyticsPage = lazyNamed(() => import('./pages/AnalyticsPage'), 'AnalyticsPage');
const ProductManagementPage = lazyNamed(() => import('./pages/ProductManagementPage'), 'ProductManagementPage');
const CustomerManagementPage = lazyNamed(() => import('./pages/CustomerManagementPage'), 'CustomerManagementPage');
const CustomerProfilePage = lazyNamed(() => import('./pages/CustomerManagementPage'), 'CustomerProfilePage');
const InventoryPage = lazyNamed(() => import('./pages/InventoryPage'), 'InventoryPage');
const PaymentsPage = lazyNamed(() => import('./pages/PaymentsPage'), 'PaymentsPage');
const ShippingPage = lazyNamed(() => import('./pages/ShippingPage'), 'ShippingPage');
const DiscountsPage = lazyNamed(() => import('./pages/DiscountsPage'), 'DiscountsPage');
const SettingsPage = lazyNamed(() => import('./pages/SettingsPage'), 'SettingsPage');
const WishlistPage = lazyNamed(() => import('./pages/WishlistPage'), 'WishlistPage');
const ComparePage = lazyNamed(() => import('./pages/ComparePage'), 'ComparePage');

export default function App() {
    return <Suspense fallback={<div className="route-loader"><Loader label="Loading page"/></div>}>
      <Routes>
        <Route element={<StoreLayout />}>
          <Route index element={<HomePage />}/>
          <Route path="products" element={<ProductListPage />}/>
          <Route path="products/:slug" element={<ProductDetailPage />}/>
          <Route path="compare" element={<ComparePage />}/>
          <Route path="login" element={<LoginPage />}/>
          <Route path="register" element={<RegisterPage />}/>
          <Route path="forgot-password" element={<ForgotPasswordPage />}/>
          <Route path="reset-password/:uid/:token" element={<ResetPasswordPage />}/>
          <Route path="auth/social/callback" element={<SocialAuthCallbackPage />}/>
          <Route element={<ProtectedRoute />}>
            <Route path="cart" element={<CartPage />}/>
            <Route path="wishlist" element={<WishlistPage />}/>
            <Route path="checkout" element={<CheckoutPage />}/>
            <Route path="checkout/confirmation/:orderId" element={<ConfirmationPage />}/>
            <Route path="account" element={<AccountPage />}/>
            <Route path="account/orders" element={<OrdersPage />}/>
            <Route path="account/orders/:id" element={<OrderDetailPage />}/>
            <Route element={<StaffDashboardLayout/>}>
              <Route path="staff/dashboard" element={<AnalyticsPage />}/>
              <Route path="staff/analytics" element={<AnalyticsPage />}/>
              <Route path="staff/orders" element={<OrdersPage />}/>
              <Route path="staff/orders/:id" element={<OrderDetailPage />}/>
              <Route path="staff/payments" element={<PaymentsPage />}/>
              <Route path="staff/shipping" element={<ShippingPage />}/>
              <Route path="staff/discounts" element={<DiscountsPage />}/>
              <Route path="staff/customers" element={<CustomerManagementPage />}/>
              <Route path="staff/customers/:id" element={<CustomerProfilePage />}/>
              <Route path="staff/inventory" element={<InventoryPage />}/>
              <Route path="staff/products" element={<ProductManagementPage />}/>
              <Route path="staff/settings" element={<SettingsPage />}/>
            </Route>
          </Route>
          <Route path="*" element={<NotFoundPage />}/>
        </Route>
      </Routes>
    </Suspense>;
}
