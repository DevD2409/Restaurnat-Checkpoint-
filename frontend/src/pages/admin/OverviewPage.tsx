import React, { useState, useEffect } from 'react';
import {
  DollarSign, ShoppingBag, Users, Clock, Flame,
  TrendingUp, ArrowUpRight, Grid, AlertCircle
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar
} from 'recharts';
import { analyticsApi, orderApi } from '../../services/api';
import { useWebSocket } from '../../context/WebSocketContext';
import { AnalyticsResponse, Order } from '../../types';

export const OverviewPage: React.FC = () => {
  const { lastEvent, connectChannel } = useWebSocket();
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchOverview = async () => {
    try {
      const [overviewData, ordersData] = await Promise.all([
        analyticsApi.getOverview(),
        orderApi.getAll({ limit: 6 }),
      ]);
      setData(overviewData);
      setRecentOrders(ordersData);
    } catch (err) {
      console.error('Failed to load overview analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    connectChannel('admin');
    fetchOverview();
  }, []);

  // Update on WebSocket event
  useEffect(() => {
    if (!lastEvent) return;
    if (
      lastEvent.type === 'ORDER_PLACED' ||
      lastEvent.type === 'ORDER_STATUS_CHANGED' ||
      lastEvent.type === 'PAYMENT_SUCCESS'
    ) {
      fetchOverview();
    }
  }, [lastEvent]);

  if (loading || !data) {
    return (
      <div className="py-20 text-center animate-fade-in">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-xs text-zinc-400">Loading live operational overview...</p>
      </div>
    );
  }

  const { kpis, daily_sales, peak_hours } = data;

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Revenue */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
              Total Revenue
            </span>
            <div className="w-9 h-9 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center">
              <DollarSign className="w-5 h-5" />
            </div>
          </div>
          <span className="text-2xl font-black text-white block">
            ₹{kpis.total_revenue.toLocaleString('en-IN')}
          </span>
          <span className="text-xs text-emerald-400 font-semibold flex items-center space-x-1 mt-1">
            <ArrowUpRight className="w-3.5 h-3.5" />
            <span>Dynamic DB verified payments</span>
          </span>
        </div>

        {/* Total Orders */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
              Total Orders
            </span>
            <div className="w-9 h-9 rounded-xl bg-brand-500/15 text-brand-400 flex items-center justify-center">
              <ShoppingBag className="w-5 h-5" />
            </div>
          </div>
          <span className="text-2xl font-black text-white block">
            {kpis.total_orders}
          </span>
          <span className="text-xs text-zinc-400 mt-1 block">
            Avg Ticket: <strong className="text-white">₹{kpis.average_order_value}</strong>
          </span>
        </div>

        {/* Table Occupancy */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
              Table Occupancy
            </span>
            <div className="w-9 h-9 rounded-xl bg-blue-500/15 text-blue-400 flex items-center justify-center">
              <Grid className="w-5 h-5" />
            </div>
          </div>
          <span className="text-2xl font-black text-white block">
            {kpis.occupancy_rate}%
          </span>
          <span className="text-xs text-zinc-400 mt-1 block">
            <strong className="text-white">{kpis.active_tables}</strong> of {kpis.total_tables} tables occupied
          </span>
        </div>

        {/* Pending Orders & Kitchen Speed */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
              Kitchen Dispatch
            </span>
            <div className="w-9 h-9 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <span className="text-2xl font-black text-amber-400 block">
            {kpis.pending_orders} Active
          </span>
          <span className="text-xs text-zinc-400 mt-1 block">
            Avg Prep Time: <strong className="text-white">{kpis.average_prep_time_minutes} mins</strong>
          </span>
        </div>
      </div>

      {/* Main Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sales Trend Chart */}
        <div className="lg:col-span-2 bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-sm text-white">Daily Revenue Trend (Past 7 Days)</h3>
              <p className="text-xs text-zinc-400">Total billings collected across digital dining channels</p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={daily_sales}>
                <defs>
                  <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f97316" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#52525b" fontSize={11} tickLine={false} />
                <YAxis stroke="#52525b" fontSize={11} tickLine={false} tickFormatter={(v) => `₹${v}`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#181924', borderColor: '#27272a', borderRadius: '12px' }}
                  labelStyle={{ color: '#ffffff', fontWeight: 'bold' }}
                />
                <Area type="monotone" dataKey="revenue" stroke="#f97316" strokeWidth={2.5} fillOpacity={1} fill="url(#revGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Peak Hours Traffic */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
          <div>
            <h3 className="font-bold text-sm text-white">Peak Dining Hours</h3>
            <p className="text-xs text-zinc-400">Hourly order frequency throughout service</p>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={peak_hours}>
                <XAxis dataKey="hour" stroke="#52525b" fontSize={10} tickLine={false} />
                <YAxis stroke="#52525b" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#181924', borderColor: '#27272a', borderRadius: '12px' }}
                />
                <Bar dataKey="order_count" fill="#ea580c" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Live Recent Orders Activity Feed */}
      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl">
        <h3 className="font-bold text-sm text-white mb-4">Recent Live Orders Activity</h3>
        <div className="divide-y divide-zinc-800 text-xs">
          {recentOrders.map((ord) => (
            <div key={ord.id} className="py-3 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <span className="font-bold text-white px-2 py-0.5 rounded-lg bg-zinc-800 border border-zinc-700">
                  {ord.order_number}
                </span>
                <div>
                  <span className="font-semibold text-zinc-200 block">
                    Table {ord.table_number || ord.table_id} ({ord.customer_name})
                  </span>
                  <span className="text-[10px] text-zinc-500">
                    {new Date(ord.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <span className="font-bold text-brand-400">₹{ord.total_amount}</span>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-zinc-800 text-zinc-300 border border-zinc-700">
                  {ord.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

