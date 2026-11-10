from pydantic import BaseModel
from typing import List, Optional

class DashboardKPIs(BaseModel):
    total_revenue: float
    total_orders: int
    active_tables: int
    total_tables: int
    occupancy_rate: float
    total_customers: int
    average_order_value: float
    pending_orders: int
    average_prep_time_minutes: float

class SalesTrendPoint(BaseModel):
    date: str
    revenue: float
    orders_count: int

class CategorySalesPoint(BaseModel):
    category_name: str
    revenue: float
    items_sold: int
    percentage: float

class TopDishPoint(BaseModel):
    dish_name: str
    category: str
    quantity_sold: int
    revenue: float

class HourlyTrafficPoint(BaseModel):
    hour: str
    order_count: int
    revenue: float

class AnalyticsResponse(BaseModel):
    kpis: DashboardKPIs
    daily_sales: List[SalesTrendPoint]
    category_sales: List[CategorySalesPoint]
    top_selling_dishes: List[TopDishPoint]
    least_selling_dishes: List[TopDishPoint]
    peak_hours: List[HourlyTrafficPoint]

