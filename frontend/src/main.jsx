import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './auth/AuthProvider';
import { CartProvider } from './components/CartProvider';
import { ToastProvider } from './components/ToastProvider';
import { WishlistProvider } from './components/WishlistProvider';
import 'react-toastify/dist/ReactToastify.css';
import './styles.css';
createRoot(document.getElementById('root')).render(<StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <CartProvider>
            <WishlistProvider>
              <App />
            </WishlistProvider>
          </CartProvider>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>);
