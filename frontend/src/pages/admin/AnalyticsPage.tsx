import React, { useState, useEffect } from 'react';
import {
  TrendingUp, Award, AlertCircle, PieChart as PieIcon,
  BarChart3, Calendar, ArrowUpRight
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { analyticsApi } from '../../services/api';
import { AnalyticsResponse } from '../../types';

export const AnalyticsPage: React.FC = () => {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const res = await analyticsApi.getOverview();
        setData(res);
      } catch (err) {
        console.error('Failed to load analytics:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchAnalytics();
  }, []);

  if (loading || !data) {
    return (
      <div className="py-20 text-center animate-fade-in">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-xs text-zinc-400">Compiling sales analytics & performance records...</p>
      </div>
    );
  }

  const { category_sales, top_selling_dishes, least_selling_dishes, daily_sales } = data;
  const PIE_COLORS = ['#f97316', '#3b82f6', '#10b981', '#a855f7', '#eab308'];

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Category Sales & Product Mix */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Revenue Breakdown */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
          <div className="flex items-center space-x-2">
            <PieIcon className="w-4 h-4 text-brand-400" />
            <h3 className="font-bold text-sm text-white">Category Sales Distribution</h3>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={category_sales}
                  dataKey="revenue"
                  nameKey="category_name"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={4}
                  fill="#8884d8"
                >
                  {category_sales.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} stroke="#12131a" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#181924', borderColor: '#27272a', borderRadius: '12px' }}
                  formatter={(val: any) => [`₹${val}`, 'Revenue']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-2 pt-2 border-t border-zinc-800/80 text-xs">
            {category_sales.map((cat, i) => (
              <div key={cat.category_name} className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                  ></span>
                  <span className="text-zinc-300 font-medium">{cat.category_name}</span>
                </div>
                <span className="font-bold text-white">₹{cat.revenue.toLocaleString('en-IN')}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Top-Selling Dishes */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
          <div className="flex items-center space-x-2">
            <Award className="w-4 h-4 text-amber-400" />
            <h3 className="font-bold text-sm text-white">Top-Selling Dishes</h3>
          </div>

          <div className="space-y-3">
            {top_selling_dishes.map((dish, idx) => (
              <div
                key={dish.dish_name}
                className="p-3 rounded-2xl bg-zinc-900 border border-zinc-800/80 flex items-center justify-between text-xs"
              >
                <div className="flex items-center space-x-3">
                  <span className="w-6 h-6 rounded-lg bg-amber-500/20 text-amber-400 font-extrabold flex items-center justify-center text-xs">
                    #{idx + 1}
                  </span>
                  <div>
                    <span className="font-bold text-zinc-100 block">{dish.dish_name}</span>
                    <span className="text-[10px] text-zinc-500">{dish.quantity_sold} orders delivered</span>
                  </div>
                </div>

                <span className="font-black text-brand-400">₹{dish.revenue}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Least Selling Dishes */}
      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl">
        <h3 className="font-bold text-sm text-white mb-2">Menu Optimization: Least-Selling Dishes</h3>
        <p className="text-xs text-zinc-400 mb-4">
          Dishes with lowest recent sales velocity. Consider repositioning or marketing promotions.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {least_selling_dishes.map((dish) => (
            <div
              key={dish.dish_name}
              className="p-3.5 rounded-2xl bg-zinc-900/60 border border-zinc-800 text-xs"
            >
              <span className="font-bold text-zinc-200 block truncate">{dish.dish_name}</span>
              <div className="flex justify-between items-center mt-2 text-zinc-400 text-[11px]">
                <span>Sold: {dish.quantity_sold} units</span>
                <span className="font-bold text-zinc-300">₹{dish.revenue}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
