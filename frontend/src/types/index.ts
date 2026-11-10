export type UserRole = 'ADMIN' | 'MANAGER' | 'WAITER' | 'KITCHEN' | 'CASHIER';

export interface User {
  id: number;
  restaurant_id: number;
  email: string;
  username: string;
  full_name: string;
  role: UserRole;
  phone_number?: string;
  is_active: boolean;
}

export interface Restaurant {
  id: number;
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
  wifi_ssid?: string;
  wifi_password?: string;
  wifi_instructions?: string;
  opening_time?: string;
  closing_time?: string;
  is_active: boolean;
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

