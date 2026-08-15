import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './auth/AuthProvider';
import { CartProvider } from './components/CartProvider';
import { ToastProvider } from './components/ToastProvider';
import { WishlistProvider } from './components/WishlistProvider';
import { CompareProvider } from './components/CompareProvider';
import 'react-toastify/dist/ReactToastify.css';
import './styles.css';
createRoot(document.getElementById('root')).render(<StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <CartProvider>
            <CompareProvider>
              <WishlistProvider>
                <App />
              </WishlistProvider>
            </CompareProvider>
          </CartProvider>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>);
