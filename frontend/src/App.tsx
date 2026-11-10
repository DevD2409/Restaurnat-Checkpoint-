import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import { WebSocketProvider } from './context/WebSocketContext';

// Layouts
import { CustomerLayout } from './layouts/CustomerLayout';
import { AdminLayout } from './layouts/AdminLayout';
import { KitchenLayout } from './layouts/KitchenLayout';

// Customer Pages
import { MenuPage } from './pages/customer/MenuPage';
import { CartPage } from './pages/customer/CartPage';
import { OrderTrackingPage } from './pages/customer/OrderTrackingPage';
import { WifiPage } from './pages/customer/WifiPage';
import { SplitBillPage } from './pages/customer/SplitBillPage';
import { ReservationPage } from './pages/customer/ReservationPage';

// Kitchen Pages
import { KitchenDisplayPage } from './pages/kitchen/KitchenDisplayPage';

// Staff Pages
import { StaffDashboardPage } from './pages/staff/StaffDashboardPage';

// Admin Pages
import { OverviewPage } from './pages/admin/OverviewPage';
import { AnalyticsPage } from './pages/admin/AnalyticsPage';
import { MenuManagementPage } from './pages/admin/MenuManagementPage';
import { TableManagementPage } from './pages/admin/TableManagementPage';
import { StaffManagementPage } from './pages/admin/StaffManagementPage';
import { ReservationsAdminPage } from './pages/admin/ReservationsAdminPage';
import { BillingAdminPage } from './pages/admin/BillingAdminPage';
import { RestaurantSettingsPage } from './pages/admin/RestaurantSettingsPage';

// Auth Pages
import { LoginPage } from './pages/auth/LoginPage';

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <WebSocketProvider>
          <CartProvider>
            <Routes>
              {/* Home redirect */}
              <Route path="/" element={<Navigate to="/menu" replace />} />

              {/* Customer QR Routes */}
              <Route path="/table/:qrToken" element={<CustomerLayout />}>
                <Route index element={<MenuPage />} />
                <Route path="cart" element={<CartPage />} />
                <Route path="track/:orderId" element={<OrderTrackingPage />} />
                <Route path="wifi" element={<WifiPage />} />
                <Route path="split-bill" element={<SplitBillPage />} />
                <Route path="reserve" element={<ReservationPage />} />
              </Route>

              {/* Customer Fallback Routes */}
              <Route path="/menu" element={<CustomerLayout />}>
                <Route index element={<MenuPage />} />
                <Route path="cart" element={<CartPage />} />
                <Route path="track/:orderId" element={<OrderTrackingPage />} />
                <Route path="wifi" element={<WifiPage />} />
                <Route path="split-bill" element={<SplitBillPage />} />
                <Route path="reserve" element={<ReservationPage />} />
              </Route>

              {/* Kitchen Display System */}
              <Route path="/kitchen" element={<KitchenLayout />}>
                <Route index element={<KitchenDisplayPage />} />
              </Route>

              {/* Staff / Waiter Portal */}
              <Route path="/staff" element={<StaffDashboardPage />} />

              {/* Restaurant Administration */}
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<Navigate to="/admin/overview" replace />} />
                <Route path="overview" element={<OverviewPage />} />
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="menu" element={<MenuManagementPage />} />
                <Route path="tables" element={<TableManagementPage />} />
                <Route path="staff" element={<StaffManagementPage />} />
                <Route path="reservations" element={<ReservationsAdminPage />} />
                <Route path="billing" element={<BillingAdminPage />} />
                <Route path="settings" element={<RestaurantSettingsPage />} />
              </Route>

              {/* Staff Authentication */}
              <Route path="/login" element={<LoginPage />} />

              {/* Catch-all */}
              <Route path="*" element={<Navigate to="/menu" replace />} />
            </Routes>
          </CartProvider>
        </WebSocketProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
