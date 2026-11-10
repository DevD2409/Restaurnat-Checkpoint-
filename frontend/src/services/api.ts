import axios from 'axios';
import {
  User, Restaurant, Table, MenuCategory, MenuItem,
  Order, ServiceRequest, Reservation, Bill, BillSplit,
  AnalyticsResponse, ServiceRequestStatus, OrderStatus
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intercept to add JWT Authorization header if available
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth & Staff API
export const authApi = {
  login: async (credentials: { username: string; password: string }) => {
    const res = await apiClient.post('/auth/login', credentials);
    return res.data;
  },
  getMe: async () => {
    const res = await apiClient.get<User>('/auth/me');
    return res.data;
  },
  listStaff: async () => {
    const res = await apiClient.get<User[]>('/auth/staff');
    return res.data;
  },
  createStaff: async (staffData: any) => {
    const res = await apiClient.post<User>('/auth/staff', staffData);
    return res.data;
  },
  updateStaff: async (id: number, staffData: any) => {
    const res = await apiClient.put<User>(`/auth/staff/${id}`, staffData);
    return res.data;
  },
  deleteStaff: async (id: number) => {
    const res = await apiClient.delete(`/auth/staff/${id}`);
    return res.data;
  },
};

// Restaurant Profile API
export const restaurantApi = {
  getProfile: async () => {
    const res = await apiClient.get<Restaurant>('/restaurants/');
    return res.data;
  },
  updateProfile: async (data: Partial<Restaurant>) => {
    const res = await apiClient.put<Restaurant>('/restaurants/', data);
    return res.data;
  },
};

// Tables & QR API
export const tableApi = {
  getAll: async () => {
    const res = await apiClient.get<Table[]>('/tables/');
    return res.data;
  },
  create: async (data: Partial<Table>) => {
    const res = await apiClient.post<Table>('/tables/', data);
    return res.data;
  },
  update: async (id: number, data: Partial<Table>) => {
    const res = await apiClient.put<Table>(`/tables/${id}`, data);
    return res.data;
  },
  validateQR: async (qr_token: string) => {
    const res = await apiClient.post('/tables/validate-qr', { qr_token });
    return res.data;
  },
  createSession: async (tableId: number, sessionData: { customer_name: string; customer_phone?: string; guest_count: number }) => {
    const res = await apiClient.post(`/tables/${tableId}/session`, sessionData);
    return res.data;
  },
  endSession: async (tableId: number) => {
    const res = await apiClient.post(`/tables/${tableId}/session/end`);
    return res.data;
  },
  getQRUrl: (tableId: number) => `${API_BASE}/tables/${tableId}/qr-code-image`,
};

// Menu API
export const menuApi = {
  getCategories: async (includeInactive = false) => {
    const res = await apiClient.get<MenuCategory[]>(`/menu/categories?include_inactive=${includeInactive}`);
    return res.data;
  },
  createCategory: async (data: any) => {
    const res = await apiClient.post<MenuCategory>('/menu/categories', data);
    return res.data;
  },
  updateCategory: async (id: number, data: any) => {
    const res = await apiClient.put<MenuCategory>(`/menu/categories/${id}`, data);
    return res.data;
  },
  deleteCategory: async (id: number) => {
    const res = await apiClient.delete(`/menu/categories/${id}`);
    return res.data;
  },
  getItems: async (params?: { category_id?: number; is_veg?: boolean; search?: string; available_only?: boolean }) => {
    const res = await apiClient.get<MenuItem[]>('/menu/items', { params });
    return res.data;
  },
  createItem: async (data: any) => {
    const res = await apiClient.post<MenuItem>('/menu/items', data);
    return res.data;
  },
  updateItem: async (id: number, data: any) => {
    const res = await apiClient.put<MenuItem>(`/menu/items/${id}`, data);
    return res.data;
  },
  deleteItem: async (id: number) => {
    const res = await apiClient.delete(`/menu/items/${id}`);
    return res.data;
  },
  toggleAvailability: async (id: number) => {
    const res = await apiClient.patch(`/menu/items/${id}/toggle-availability`);
    return res.data;
  },
};

// Orders API
export const orderApi = {
  create: async (orderData: any) => {
    const res = await apiClient.post<Order>('/orders/', orderData);
    return res.data;
  },
  getAll: async (params?: { status?: string; table_id?: number; limit?: number }) => {
    const res = await apiClient.get<Order[]>('/orders/', { params });
    return res.data;
  },
  getById: async (id: number) => {
    const res = await apiClient.get<Order>(`/orders/${id}`);
    return res.data;
  },
  updateStatus: async (id: number, status: OrderStatus, notes?: string, changed_by?: string) => {
    const res = await apiClient.patch<Order>(`/orders/${id}/status`, { status, notes, changed_by });
    return res.data;
  },
  updatePriority: async (id: number, priority: string) => {
    const res = await apiClient.patch<Order>(`/orders/${id}/priority`, { priority });
    return res.data;
  },
};

// Kitchen KDS API
export const kitchenApi = {
  getActiveOrders: async () => {
    const res = await apiClient.get('/kitchen/active');
    return res.data;
  },
  updateStatus: async (orderId: number, status: string, chefName?: string) => {
    const res = await apiClient.post('/kitchen/update-status', {
      order_id: orderId,
      status,
      chef_name: chefName || 'Kitchen Chef'
    });
    return res.data;
  },
};

// Service Requests API
export const serviceRequestApi = {
  create: async (data: { table_id: number; request_type: string; customer_notes?: string; restaurant_id?: number }) => {
    const res = await apiClient.post<ServiceRequest>('/service-requests/', data);
    return res.data;
  },
  getAll: async (status?: ServiceRequestStatus, tableId?: number) => {
    const res = await apiClient.get<ServiceRequest[]>('/service-requests/', {
      params: { status, table_id: tableId }
    });
    return res.data;
  },
  updateStatus: async (id: number, status: ServiceRequestStatus, staff_notes?: string, assigned_staff_id?: number) => {
    const res = await apiClient.patch<ServiceRequest>(`/service-requests/${id}/status`, {
      status,
      staff_notes,
      assigned_staff_id
    });
    return res.data;
  },
};

// Reservations API
export const reservationApi = {
  create: async (data: any) => {
    const res = await apiClient.post<Reservation>('/reservations/', data);
    return res.data;
  },
  getAll: async (params?: { date?: string; status?: string }) => {
    const res = await apiClient.get<Reservation[]>('/reservations/', { params });
    return res.data;
  },
  updateStatus: async (id: number, data: { status: string; table_id?: number; special_requests?: string }) => {
    const res = await apiClient.patch<Reservation>(`/reservations/${id}/status`, data);
    return res.data;
  },
};

// Billing & Payments API
export const billingApi = {
  getBillForOrder: async (orderId: number) => {
    const res = await apiClient.get<Bill>(`/billing/order/${orderId}`);
    return res.data;
  },
  getBill: async (billId: number) => {
    const res = await apiClient.get<Bill>(`/billing/${billId}`);
    return res.data;
  },
  configureSplits: async (billId: number, splits: any[]) => {
    const res = await apiClient.post<BillSplit[]>(`/billing/${billId}/splits`, splits);
    return res.data;
  },
  getReceipt: async (billId: number) => {
    const res = await apiClient.get(`/billing/${billId}/receipt`);
    return res.data;
  },
  createRazorpayOrder: async (billId: number, amount: number) => {
    const res = await apiClient.post('/payments/razorpay-order', {
      bill_id: billId,
      amount
    });
    return res.data;
  },
  verifyRazorpayPayment: async (data: {
    bill_id: number;
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
    amount: number;
    split_id?: number;
  }) => {
    const res = await apiClient.post('/payments/verify-razorpay-payment', data);
    return res.data;
  },
  recordOfflinePayment: async (billId: number, amount: number, paymentMethod: 'CASH' | 'CARD') => {
    const res = await apiClient.post('/payments/offline-payment', {
      bill_id: billId,
      amount,
      payment_method: paymentMethod
    });
    return res.data;
  },
  refundPayment: async (paymentId: number, amount?: number, reason?: string) => {
    const res = await apiClient.post('/payments/refund', {
      payment_id: paymentId,
      amount,
      reason
    });
    return res.data;
  },
  reconcile: async (billId: number) => {
    const res = await apiClient.get(`/payments/reconcile/${billId}`);
    return res.data;
  },
};

// Subscriptions & SaaS Ledger API (Flow B)
export const subscriptionsApi = {
  getPlans: async () => {
    const res = await apiClient.get('/subscriptions/plans');
    return res.data;
  },
  validateCoupon: async (code: string, planCode: string, restaurantId?: number) => {
    const res = await apiClient.post('/subscriptions/coupons/validate', {
      code,
      plan_code: planCode,
      restaurant_id: restaurantId
    });
    return res.data;
  },
  previewCheckout: async (planCode: string, couponCode?: string, restaurantId?: number) => {
    const res = await apiClient.post('/subscriptions/checkout/preview', {
      plan_code: planCode,
      coupon_code: couponCode,
      restaurant_id: restaurantId
    });
    return res.data;
  },
  checkout: async (data: {
    restaurant_id?: number;
    plan_code: string;
    coupon_code?: string;
  }) => {
    const res = await apiClient.post('/subscriptions/checkout', data);
    return res.data;
  },
  verifyPayment: async (data: {
    invoice_id: number;
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }) => {
    const res = await apiClient.post('/subscriptions/verify', data);
    return res.data;
  },
  getMyStatus: async () => {
    const res = await apiClient.get('/subscriptions/my-status');
    return res.data;
  },
  getInvoices: async () => {
    const res = await apiClient.get('/subscriptions/invoices');
    return res.data;
  },
  getNotifications: async () => {
    const res = await apiClient.get('/subscriptions/notifications');
    return res.data;
  },
  getAdminAnalytics: async () => {
    const res = await apiClient.get('/subscriptions/admin/analytics');
    return res.data;
  },
  createPlan: async (planData: any) => {
    const res = await apiClient.post('/subscriptions/admin/plans', planData);
    return res.data;
  },
  togglePlan: async (planId: number, isActive: boolean) => {
    const res = await apiClient.patch(`/subscriptions/admin/plans/${planId}?is_active=${isActive}`);
    return res.data;
  },
  listCoupons: async () => {
    const res = await apiClient.get('/subscriptions/admin/coupons');
    return res.data;
  },
  createCoupon: async (couponData: any) => {
    const res = await apiClient.post('/subscriptions/admin/coupons', couponData);
    return res.data;
  },
  toggleCoupon: async (couponId: number, isActive: boolean) => {
    const res = await apiClient.patch(`/subscriptions/admin/coupons/${couponId}?is_active=${isActive}`);
    return res.data;
  },
  evaluateExpiries: async () => {
    const res = await apiClient.post('/subscriptions/admin/evaluate-expiries');
    return res.data;
  },
  refund: async (paymentId: number, amountPaise?: number, reason?: string) => {
    const res = await apiClient.post('/subscriptions/refund', {
      payment_id: paymentId,
      amount_paise: amountPaise,
      reason
    });
    return res.data;
  },
};

// Analytics API
export const analyticsApi = {
  getOverview: async () => {
    const res = await apiClient.get<AnalyticsResponse>('/analytics/overview');
    return res.data;
  },
};
