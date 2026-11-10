export type UserRole =
  | 'PLATFORM_SUPER_ADMIN'
  | 'RESTAURANT_OWNER'
  | 'RESTAURANT_MANAGER'
  | 'ADMIN'
  | 'MANAGER'
  | 'WAITER'
  | 'KITCHEN'
  | 'CASHIER'
  | 'CUSTOMER';

export interface User {
  id: number;
  restaurant_id?: number | null;
  restaurant_slug?: string;
  email: string;
  username: string;
  full_name: string;
  role: UserRole;
  phone_number?: string;
  shift?: string;
  is_active: boolean;
}

export interface Restaurant {
  id: number;
  slug?: string;
  name: string;
  tagline?: string;
  address?: string;
  phone?: string;
  email?: string;
  gst_number?: string;
  tax_percentage: number;
  service_charge_percentage: number;
  currency: string;
  currency_symbol: string;
  timezone?: string;
  logo_url?: string;
  cover_image_url?: string;
  primary_color?: string;
  secondary_color?: string;
  facilities?: string;
  service_types?: string;
  razorpay_key_id?: string;
  razorpay_key_secret_enc?: string;
  subscription_plan?: string;
  subscription_status?: string;
  owner_id?: number;
  wifi_ssid?: string;
  wifi_password?: string;
  wifi_instructions?: string;
  opening_time?: string;
  closing_time?: string;
  is_active: boolean;
}

export interface RestaurantPublicProfile {
  id: number;
  slug: string;
  name: string;
  tagline?: string;
  address?: string;
  phone?: string;
  email?: string;
  tax_percentage: number;
  service_charge_percentage: number;
  currency: string;
  currency_symbol: string;
  logo_url?: string;
  cover_image_url?: string;
  primary_color: string;
  facilities?: string;
  service_types?: string;
  wifi_ssid?: string;
  opening_time?: string;
  closing_time?: string;
}

export interface Feedback {
  id: number;
  restaurant_id: number;
  customer_name: string;
  overall_rating: number;
  rating?: number;
  food_rating?: number;
  service_rating?: number;
  ambience_rating?: number;
  cleanliness_rating?: number;
  comment?: string;
  created_at: string;
}

export interface PlatformStats {
  total_tenants: number;
  total_restaurants: number;
  active_tenants: number;
  total_platform_orders: number;
  total_platform_revenue: number;
  total_registered_users: number;
  subscription_plans?: Record<string, number>;
  subscription_breakdown?: Record<string, number>;
}

export interface PlatformTenant {
  id: number;
  name: string;
  slug: string;
  subscription_plan: string;
  subscription_status: string;
  is_active: boolean;
  owner_username?: string;
  owner_email?: string;
  total_orders: number;
  total_tables: number;
  total_revenue: number;
  created_at?: string;
}

export type TableStatus =
  | 'Available'
  | 'Occupied'
  | 'Reserved'
  | 'Cleaning'
  | 'Order Pending'
  | 'Bill Requested';

export interface Table {
  id: number;
  restaurant_id: number;
  table_number: string;
  capacity: number;
  section: string;
  status: TableStatus;
  pos_x: number;
  pos_y: number;
  qr_token?: string;
  current_session_id?: number;
  is_active: boolean;
  active_order_id?: number;
  active_bill_amount?: number;
  session_start_time?: string;
}

export interface TableSession {
  id: number;
  table_id: number;
  customer_name: string;
  customer_phone?: string;
  guest_count: number;
  session_token: string;
  is_active: boolean;
  started_at: string;
  table_number?: string;
}

export interface MenuCustomizationOption {
  id?: number;
  name: string;
  additional_price: number;
  is_default: boolean;
}

export interface MenuCustomizationGroup {
  id?: number;
  group_name: string;
  is_required: boolean;
  min_select: number;
  max_select: number;
  options: MenuCustomizationOption[];
}

export interface MenuItem {
  id: number;
  category_id: number;
  name: string;
  description?: string;
  price: number;
  is_veg: boolean;
  is_bestseller: boolean;
  is_available: boolean;
  preparation_time: number;
  calories?: number;
  dietary_tags?: string;
  spice_level?: 'Mild' | 'Medium' | 'Hot' | 'Extra Hot';
  image_url?: string;
  customization_groups?: MenuCustomizationGroup[];
}

export interface MenuCategory {
  id: number;
  restaurant_id: number;
  name: string;
  description?: string;
  icon: string;
  display_order: number;
  is_active: boolean;
  items: MenuItem[];
}

export type OrderStatus =
  | 'PLACED'
  | 'ACCEPTED'
  | 'PREPARING'
  | 'READY'
  | 'SERVED'
  | 'COMPLETED'
  | 'CANCELLED';

export type OrderPriority = 'NORMAL' | 'HIGH' | 'URGENT';
export type PaymentStatus = 'UNPAID' | 'PARTIAL' | 'PAID' | 'REFUNDED';

export interface OrderItemCustomization {
  group_name: string;
  option_name: string;
  additional_price: number;
}

export interface OrderItem {
  id: number;
  order_id: number;
  menu_item_id?: number;
  item_name: string;
  unit_price: number;
  quantity: number;
  total_price: number;
  customizations_json?: string;
  special_instructions?: string;
  status: string;
}

export interface OrderStatusHistory {
  id: number;
  previous_status?: string;
  new_status: string;
  changed_by: string;
  notes?: string;
  created_at: string;
}

export interface Order {
  id: number;
  order_number: string;
  restaurant_id: number;
  table_id: number;
  table_number?: string;
  session_id?: number;
  customer_name: string;
  customer_phone?: string;
  status: OrderStatus;
  priority: OrderPriority;
  subtotal: number;
  tax_amount: number;
  service_charge: number;
  tip_amount: number;
  total_amount: number;
  payment_status: PaymentStatus;
  special_instructions?: string;
  estimated_prep_time: number;
  actual_prep_time?: number;
  created_at: string;
  updated_at?: string;
  items: OrderItem[];
  status_history: OrderStatusHistory[];
}

export type ServiceRequestType = 'CALL_WAITER' | 'WATER' | 'CUTLERY' | 'ASSISTANCE' | 'BILL';
export type ServiceRequestStatus = 'PENDING' | 'ACKNOWLEDGED' | 'RESOLVED' | 'CANCELLED';

export interface ServiceRequest {
  id: number;
  restaurant_id: number;
  table_id: number;
  table_number?: string;
  request_type: ServiceRequestType;
  status: ServiceRequestStatus;
  customer_notes?: string;
  staff_notes?: string;
  assigned_staff_id?: number;
  assigned_staff_name?: string;
  created_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
}

export type ReservationStatus = 'PENDING' | 'CONFIRMED' | 'SEATED' | 'CANCELLED' | 'REJECTED';

export interface Reservation {
  id: number;
  restaurant_id: number;
  customer_name: string;
  customer_email?: string;
  customer_phone: string;
  guest_count: number;
  reservation_date: string;
  reservation_time: string;
  table_id?: number;
  table_number?: string;
  status: ReservationStatus;
  special_requests?: string;
  created_at: string;
}

export type BillStatus = 'UNPAID' | 'PARTIAL' | 'PAID';
export type SplitType = 'EQUAL' | 'BY_ITEM' | 'CUSTOM';
export type PaymentMethod = 'CASH' | 'CARD' | 'UPI' | 'RAZORPAY';

export interface BillSplit {
  id: number;
  bill_id: number;
  split_type: SplitType;
  person_name: string;
  amount: number;
  is_paid: boolean;
  payment_method?: string;
  transaction_id?: string;
  created_at: string;
}

export interface PaymentRecord {
  id: number;
  bill_id: number;
  amount: number;
  payment_method: PaymentMethod;
  transaction_id?: string;
  razorpay_order_id?: string;
  razorpay_payment_id?: string;
  status: string;
  created_at: string;
}

export interface Bill {
  id: number;
  bill_number: string;
  restaurant_id: number;
  order_id: number;
  table_id: number;
  table_number?: string;
  subtotal: number;
  tax_percentage: number;
  tax_amount: number;
  service_charge_percentage: number;
  service_charge: number;
  tip_amount: number;
  discount_amount: number;
  final_amount: number;
  status: BillStatus;
  created_at: string;
  splits: BillSplit[];
  payments: PaymentRecord[];
}

export interface DashboardKPIs {
  total_revenue: number;
  total_orders: number;
  active_tables: number;
  total_tables: number;
  occupancy_rate: number;
  total_customers: number;
  average_order_value: number;
  pending_orders: number;
  average_prep_time_minutes: number;
}

export interface SalesTrendPoint {
  date: string;
  revenue: number;
  orders_count: number;
}

export interface CategorySalesPoint {
  category_name: string;
  revenue: number;
  items_sold: number;
  percentage: number;
}

export interface TopDishPoint {
  dish_name: string;
  category: string;
  quantity_sold: number;
  revenue: number;
}

export interface HourlyTrafficPoint {
  hour: string;
  order_count: number;
  revenue: number;
}

export interface AnalyticsResponse {
  kpis: DashboardKPIs;
  daily_sales: SalesTrendPoint[];
  category_sales: CategorySalesPoint[];
  top_selling_dishes: TopDishPoint[];
  least_selling_dishes: TopDishPoint[];
  peak_hours: HourlyTrafficPoint[];
}

// Cart Item for Customer App
export interface CartItem {
  id: string; // composite key: `${menu_item_id}-${selectedOptionsHash}`
  menu_item_id: number;
  name: string;
  unit_price: number;
  quantity: number;
  is_veg: boolean;
  selected_customizations: OrderItemCustomization[];
  special_instructions?: string;
  image_url?: string;
}

// Subscription & SaaS Ledger Types (Flow B)
export interface SubscriptionPlan {
  id: number;
  plan_code: string;
  name: string;
  billing_cycle: string;
  price_paise: number;
  price_inr: number;
  price?: number; // fallback
  currency: string;
  duration_days: number;
  features?: string;
  entitlements?: Record<string, any>;
  max_tables: number;
  is_active: boolean;
}

export interface SubscriptionPayment {
  id: number;
  invoice_id: number;
  razorpay_payment_id?: string;
  amount_paise?: number;
  amount_inr?: number;
  amount?: number;
  currency: string;
  payment_method: string;
  status: string;
  created_at: string;
}

export interface SubscriptionInvoice {
  id: number;
  invoice_number: string;
  restaurant_id: number;
  plan_id: number;
  plan_name?: string;
  billing_cycle: string;
  subtotal_paise: number;
  subtotal_inr: number;
  subtotal?: number;
  discount_paise: number;
  discount_inr: number;
  discount_amount?: number;
  tax_percentage: number;
  tax_paise: number;
  tax_inr: number;
  tax_amount?: number;
  final_amount_paise: number;
  final_amount_inr: number;
  final_amount?: number;
  currency: string;
  status: 'UNPAID' | 'PAID' | 'VOID' | 'REFUNDED';
  billing_start_date?: string;
  billing_end_date?: string;
  paid_at?: string;
  created_at: string;
  payments?: SubscriptionPayment[];
}

export interface RestaurantSubscriptionStatus {
  restaurant_id: number;
  restaurant_name: string;
  subscription_status: 'TRIAL' | 'ACTIVE' | 'PAST_DUE' | 'EXPIRED' | 'CANCELLED' | 'SUSPENDED';
  subscription_plan?: string;
  subscription_expires_at?: string;
  grace_period_days: number;
  days_remaining?: number;
  is_in_grace_period: boolean;
  grace_period_remaining_days?: number;
  can_operate: boolean;
}

export interface SubscriptionNotification {
  id: number;
  restaurant_id: number;
  notification_type: 'RENEWAL_UPCOMING' | 'RENEWAL_SUCCESS' | 'PAST_DUE_WARNING' | 'EXPIRED' | 'PAYMENT_FAILED';
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface SubscriptionCheckoutPreview {
  plan_code: string;
  name: string;
  billing_cycle: string;
  duration_days: number;
  subtotal_paise: number;
  subtotal_inr: number;
  discount_paise: number;
  discount_inr: number;
  tax_paise: number;
  tax_inr: number;
  final_amount_paise: number;
  final_amount_inr: number;
  coupon_code?: string;
  billing_start_date: string;
  billing_end_date: string;
}


