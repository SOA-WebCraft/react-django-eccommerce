import { Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { StoreLayout } from './layouts/StoreLayout';
import { StaffDashboardLayout } from './layouts/StaffDashboardLayout';
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage, SocialAuthCallbackPage } from './pages/AuthPages';
import { CartPage } from './pages/CartPage';
import { CheckoutPage, ConfirmationPage } from './pages/CheckoutPages';
import { HomePage } from './pages/HomePage';
import { NotFoundPage } from './pages/NotFoundPage';
import { AccountPage, OrderDetailPage, OrdersPage } from './pages/OrderPages';
import { ProductDetailPage } from './pages/ProductDetailPage';
import { ProductListPage } from './pages/ProductListPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { ProductManagementPage } from './pages/ProductManagementPage';
import { CustomerManagementPage, CustomerProfilePage } from './pages/CustomerManagementPage';
import { InventoryPage } from './pages/InventoryPage';
import { PaymentsPage } from './pages/PaymentsPage';
import { ShippingPage } from './pages/ShippingPage';
import { DiscountsPage } from './pages/DiscountsPage';
import { SettingsPage } from './pages/SettingsPage';
export default function App() {
    return (<Routes>
      <Route element={<StoreLayout />}>
        <Route index element={<HomePage />}/>
        <Route path="products" element={<ProductListPage />}/>
        <Route path="products/:slug" element={<ProductDetailPage />}/>
        <Route path="login" element={<LoginPage />}/>
        <Route path="register" element={<RegisterPage />}/>
        <Route path="forgot-password" element={<ForgotPasswordPage />}/>
        <Route path="reset-password/:uid/:token" element={<ResetPasswordPage />}/>
        <Route path="auth/social/callback" element={<SocialAuthCallbackPage />}/>
        <Route element={<ProtectedRoute />}>
          <Route path="cart" element={<CartPage />}/>
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
    </Routes>);
}
