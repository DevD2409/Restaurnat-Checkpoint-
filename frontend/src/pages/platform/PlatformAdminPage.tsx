import React, { useState, useEffect } from 'react';
import { 
  Building2, Users, DollarSign, ShoppingBag, ShieldCheck, 
  ExternalLink, CheckCircle2, AlertTriangle, RefreshCw, 
  Search, Filter, ChevronRight, Crown, Power, BarChart3, ArrowUpRight,
  Tag, Calendar, Sparkles, Check, Clock, Plus, Zap
} from 'lucide-react';
import { PlatformStats, PlatformTenant } from '../../types';
import { apiClient, subscriptionsApi } from '../../services/api';

export function PlatformAdminPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [tenants, setTenants] = useState<PlatformTenant[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [coupons, setCoupons] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'tenants' | 'subscriptions' | 'coupons'>('tenants');
  
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [evaluatingExpiries, setEvaluatingExpiries] = useState(false);

  // New Coupon Form State
  const [showCouponModal, setShowCouponModal] = useState(false);
  const [newCoupon, setNewCoupon] = useState({
    code: '',
    discount_paise: 100000, // ₹1,000
    discount_type: 'FIXED_AMOUNT',
    discount_percentage: 0,
    eligible_plan_codes: '*',
    max_uses_global: 500,
    max_uses_per_restaurant: 1
  });

  const fetchPlatformData = async () => {
    try {
      setLoading(true);
      const [statsRes, tenantsRes, analyticsRes, couponsRes, plansRes] = await Promise.all([
        apiClient.get('/platform/stats'),
        apiClient.get('/platform/restaurants'),
        subscriptionsApi.getAdminAnalytics().catch(() => null),
        subscriptionsApi.listCoupons().catch(() => []),
        subscriptionsApi.getPlans().catch(() => [])
      ]);

      setStats(statsRes.data && typeof statsRes.data === 'object' ? statsRes.data : null);
      setTenants(Array.isArray(tenantsRes.data) ? tenantsRes.data : []);
      setAnalytics(analyticsRes && typeof analyticsRes === 'object' ? analyticsRes : null);
      setCoupons(Array.isArray(couponsRes) ? couponsRes : []);
      setPlans(Array.isArray(plansRes) ? plansRes : []);
    } catch (err) {
      console.error('Failed to fetch SaaS platform data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlatformData();
  }, []);

  const handleToggleSubscription = async (tenantId: number, currentStatus: string) => {
    try {
      setActionLoading(tenantId);
      const newStatus = currentStatus === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
      await apiClient.patch(
        `/platform/restaurants/${tenantId}/subscription`,
        { subscription_status: newStatus }
      );
      await fetchPlatformData();
    } catch (err) {
      console.error('Failed to update tenant status:', err);
      alert('Failed to update subscription status.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleCoupon = async (couponId: number, currentActive: boolean) => {
    try {
      await subscriptionsApi.toggleCoupon(couponId, !currentActive);
      const updated = await subscriptionsApi.listCoupons();
      setCoupons(updated);
    } catch (err) {
      alert('Failed to update coupon status');
    }
  };

  const handleCreateCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await subscriptionsApi.createCoupon(newCoupon);
      setShowCouponModal(false);
      setNewCoupon({
        code: '',
        discount_paise: 100000,
        discount_type: 'FIXED_AMOUNT',
        discount_percentage: 0,
        eligible_plan_codes: '*',
        max_uses_global: 500,
        max_uses_per_restaurant: 1
      });
      const updated = await subscriptionsApi.listCoupons();
      setCoupons(updated);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create coupon');
    }
  };

  const handleEvaluateExpiries = async () => {
    try {
      setEvaluatingExpiries(true);
      const res = await subscriptionsApi.evaluateExpiries();
      alert(`Evaluated ${res.evaluated_restaurants} restaurants. ${res.status_transitions} status transitions updated.`);
      await fetchPlatformData();
    } catch (err) {
      alert('Failed to evaluate expiries');
    } finally {
      setEvaluatingExpiries(false);
    }
  };

  const filteredTenants = tenants.filter(t => {
    const matchesSearch = 
      t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.slug.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (t.owner_email && t.owner_email.toLowerCase().includes(searchTerm.toLowerCase()));
    
    const matchesStatus = statusFilter === 'ALL' || t.subscription_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="min-h-screen bg-[#090a0f] text-slate-100 p-6 md:p-10 font-sans selection:bg-brand-500 selection:text-white">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-3 py-1 bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold rounded-full flex items-center gap-1.5">
              <Crown className="w-3.5 h-3.5 text-amber-400" />
              SaaS Super Admin Console
            </span>
            <span className="text-xs text-slate-400">SRMP Core Multi-Tenant Platform</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
            Hospitality Platform & Subscriptions
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Global monitoring, tenant MRR, coupon engine, subscription ledger, and feature gating.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchPlatformData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm font-medium transition-colors"
          >
            <RefreshCw className={`w-4 h-4 text-slate-300 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <a
            href="/onboard"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white font-medium text-sm rounded-lg shadow-lg shadow-orange-500/20 transition-all"
          >
            <Building2 className="w-4 h-4" />
            Onboard Tenant
            <ArrowUpRight className="w-3.5 h-3.5 opacity-80" />
          </a>
        </div>
      </div>

      <div className="max-w-7xl mx-auto space-y-8">
        {/* Top SaaS Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Monthly Recurring Revenue</span>
              <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <DollarSign className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white">
                ₹{analytics ? analytics.mrr_inr.toLocaleString('en-IN') : '0'}
              </span>
              <span className="text-xs text-emerald-400 font-medium">MRR</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              ARR: ₹{analytics ? analytics.arr_inr.toLocaleString('en-IN') : '0'}
            </p>
          </div>

          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Active Subscribers</span>
              <div className="w-9 h-9 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400">
                <Building2 className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white">
                {analytics?.active_tenants ?? tenants.filter(t => t.subscription_status === 'ACTIVE').length}
              </span>
              <span className="text-xs text-slate-400">
                / {tenants.length} Total
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              {analytics?.past_due_tenants ?? 0} in Grace Period • {analytics?.churn_count ?? 0} Churned
            </p>
          </div>

          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Coupons Redeemed</span>
              <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                <Tag className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white">
                {analytics?.total_coupons_redeemed ?? 0}
              </span>
              <span className="text-xs text-amber-400 font-medium">Times</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Total Discount: ₹{analytics ? analytics.total_discount_disbursed_inr.toLocaleString('en-IN') : '0'}
            </p>
          </div>

          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Guest Food Volume</span>
              <div className="w-9 h-9 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                <ShoppingBag className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white">
                ₹{stats?.total_platform_revenue ? stats.total_platform_revenue.toLocaleString('en-IN') : '0'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">Separate Restaurant Direct Flow</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveTab('tenants')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'tenants'
                  ? 'bg-orange-500 text-white shadow-md shadow-orange-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              Tenants Directory ({tenants.length})
            </button>
            <button
              onClick={() => setActiveTab('subscriptions')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'subscriptions'
                  ? 'bg-orange-500 text-white shadow-md shadow-orange-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              Subscription Plans & Grace Period
            </button>
            <button
              onClick={() => setActiveTab('coupons')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'coupons'
                  ? 'bg-orange-500 text-white shadow-md shadow-orange-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              Coupon Engine ({coupons.length})
            </button>
          </div>

          {activeTab === 'subscriptions' && (
            <button
              onClick={handleEvaluateExpiries}
              disabled={evaluatingExpiries}
              className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold rounded-lg text-amber-400 transition"
            >
              <Clock className="w-3.5 h-3.5" />
              {evaluatingExpiries ? 'Evaluating...' : 'Run Expiry & Grace Period Check'}
            </button>
          )}

          {activeTab === 'coupons' && (
            <button
              onClick={() => setShowCouponModal(true)}
              className="flex items-center gap-2 px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 text-xs font-bold rounded-lg text-white shadow-sm transition"
            >
              <Plus className="w-3.5 h-3.5" />
              Create Coupon
            </button>
          )}
        </div>

        {/* TAB 1: TENANTS DIRECTORY */}
        {activeTab === 'tenants' && (
          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by restaurant name, slug, or owner email..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-orange-500"
                />
              </div>

              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-slate-400" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 px-3 py-2 focus:outline-none focus:border-orange-500"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="ACTIVE">Active</option>
                  <option value="PAST_DUE">Past Due (Grace Period)</option>
                  <option value="EXPIRED">Expired</option>
                  <option value="SUSPENDED">Suspended</option>
                  <option value="CANCELLED">Cancelled</option>
                </select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-900/40 text-slate-400 font-medium text-xs uppercase tracking-wider">
                    <th className="py-3 px-4">Restaurant / Hotel</th>
                    <th className="py-3 px-4">Plan & Cycle</th>
                    <th className="py-3 px-4">Subscription Status</th>
                    <th className="py-3 px-4 text-center">Tables</th>
                    <th className="py-3 px-4 text-center">Orders</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredTenants.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-500">
                        No restaurants match the search criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredTenants.map((tenant) => (
                      <tr key={tenant.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-4 px-4">
                          <div className="font-semibold text-white">{tenant.name}</div>
                          <div className="text-xs text-slate-400 font-mono mt-0.5">/{tenant.slug}</div>
                        </td>
                        <td className="py-4 px-4">
                          <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-800 border border-slate-700 text-slate-200">
                            {tenant.subscription_plan || 'MONTHLY'}
                          </span>
                        </td>
                        <td className="py-4 px-4">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${
                            tenant.subscription_status === 'ACTIVE'
                              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                              : tenant.subscription_status === 'PAST_DUE'
                              ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                              : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                          }`}>
                            {tenant.subscription_status}
                          </span>
                        </td>
                        <td className="py-4 px-4 text-center font-semibold text-slate-200">{tenant.total_tables}</td>
                        <td className="py-4 px-4 text-center font-semibold text-slate-200">{tenant.total_orders}</td>
                        <td className="py-4 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <a
                              href={`/${tenant.slug}/menu`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-1.5 hover:bg-slate-700/80 rounded-lg text-slate-400 hover:text-white transition-colors"
                              title="View Customer Menu"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </a>
                            <button
                              onClick={() => handleToggleSubscription(tenant.id, tenant.subscription_status)}
                              disabled={actionLoading === tenant.id}
                              className={`p-1.5 rounded-lg border text-xs font-medium transition-colors ${
                                tenant.subscription_status === 'ACTIVE'
                                  ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 hover:bg-rose-500/20'
                                  : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                              }`}
                              title={tenant.subscription_status === 'ACTIVE' ? 'Suspend Tenant' : 'Activate Tenant'}
                            >
                              <Power className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 2: SUBSCRIPTION PLANS & ENTITLEMENTS */}
        {activeTab === 'subscriptions' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {plans.map((p) => (
                <div key={p.id} className="bg-[#12141c] border border-slate-800 rounded-xl p-6 relative overflow-hidden shadow-sm">
                  {p.plan_code === 'YEARLY' && (
                    <div className="absolute top-4 right-4 px-2.5 py-0.5 bg-amber-500/20 border border-amber-500/40 text-amber-400 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-1">
                      <Sparkles className="w-3 h-3" /> Best Value
                    </div>
                  )}
                  <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{p.billing_cycle} BILLING</div>
                  <h3 className="text-xl font-bold text-white mt-1">{p.name}</h3>
                  <div className="mt-4 flex items-baseline gap-2">
                    <span className="text-4xl font-extrabold text-white">₹{p.price_inr.toLocaleString('en-IN')}</span>
                    <span className="text-sm text-slate-400">/ {p.billing_cycle === 'YEARLY' ? 'year (12 months)' : 'month'}</span>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">Stored as {p.price_paise.toLocaleString()} paise in database</div>

                  <p className="text-sm text-slate-300 mt-4 pb-4 border-b border-slate-800">{p.features}</p>

                  <div className="mt-4 space-y-2.5">
                    <div className="text-xs font-semibold text-slate-400 uppercase">Configured Entitlements:</div>
                    <div className="flex items-center gap-2 text-sm text-slate-200">
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span>Max Tables: <strong className="text-white">{p.max_tables >= 900 ? 'Unlimited' : p.max_tables}</strong></span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-slate-200">
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span>Kitchen Display System (KDS): Included</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-slate-200">
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span>Advanced Revenue & Analytics: Included</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-slate-200">
                      <Check className="w-4 h-4 text-emerald-400" />
                      <span>Multi-Branch & Priority Support: {p.plan_code === 'YEARLY' ? 'Included' : 'Yearly tier only'}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: COUPON ENGINE */}
        {activeTab === 'coupons' && (
          <div className="bg-[#12141c] border border-slate-800 rounded-xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Promotional Coupon Codes</h3>
                <p className="text-xs text-slate-400">Fixed discounts, eligible plans, usage limits, and active status.</p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-900/40 text-slate-400 font-medium text-xs uppercase tracking-wider">
                    <th className="py-3 px-4">Coupon Code</th>
                    <th className="py-3 px-4">Discount Value</th>
                    <th className="py-3 px-4">Eligible Plans</th>
                    <th className="py-3 px-4 text-center">Usage Limits</th>
                    <th className="py-3 px-4 text-center">Times Used</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {coupons.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-4 px-4 font-mono font-bold text-amber-400">{c.code}</td>
                      <td className="py-4 px-4 font-semibold text-white">
                        {c.discount_type === 'PERCENTAGE'
                          ? `${c.discount_percentage}% OFF`
                          : `₹${c.discount_inr.toLocaleString('en-IN')} OFF (${c.discount_paise} paise)`
                        }
                      </td>
                      <td className="py-4 px-4">
                        <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-300">
                          {c.eligible_plan_codes}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-center text-xs text-slate-300">
                        Global: {c.max_uses_global} • Rest: {c.max_uses_per_restaurant}
                      </td>
                      <td className="py-4 px-4 text-center font-bold text-white">{c.times_used}</td>
                      <td className="py-4 px-4">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${
                          c.is_active ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-slate-800 border-slate-700 text-slate-400'
                        }`}>
                          {c.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-right">
                        <button
                          onClick={() => handleToggleCoupon(c.id, c.is_active)}
                          className={`px-2.5 py-1 rounded text-xs font-semibold border transition ${
                            c.is_active 
                              ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 hover:bg-rose-500/20' 
                              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                          }`}
                        >
                          {c.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Create Coupon Modal */}
      {showCouponModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#12141c] border border-slate-700 rounded-xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-4">Create Promo Coupon</h3>
            <form onSubmit={handleCreateCoupon} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-300">Coupon Code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. LAUNCH20"
                  value={newCoupon.code}
                  onChange={(e) => setNewCoupon({ ...newCoupon, code: e.target.value.toUpperCase() })}
                  className="w-full mt-1 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300">Discount Amount in Paise (e.g. 20000 = ₹200)</label>
                <input
                  type="number"
                  required
                  value={newCoupon.discount_paise}
                  onChange={(e) => setNewCoupon({ ...newCoupon, discount_paise: parseInt(e.target.value) || 0 })}
                  className="w-full mt-1 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300">Eligible Plans (e.g. MONTHLY, YEARLY, or *)</label>
                <input
                  type="text"
                  required
                  value={newCoupon.eligible_plan_codes}
                  onChange={(e) => setNewCoupon({ ...newCoupon, eligible_plan_codes: e.target.value.toUpperCase() })}
                  className="w-full mt-1 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300">Global Limit</label>
                  <input
                    type="number"
                    value={newCoupon.max_uses_global}
                    onChange={(e) => setNewCoupon({ ...newCoupon, max_uses_global: parseInt(e.target.value) || 100 })}
                    className="w-full mt-1 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300">Per Restaurant</label>
                  <input
                    type="number"
                    value={newCoupon.max_uses_per_restaurant}
                    onChange={(e) => setNewCoupon({ ...newCoupon, max_uses_per_restaurant: parseInt(e.target.value) || 1 })}
                    className="w-full mt-1 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCouponModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg text-sm hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white font-bold rounded-lg text-sm shadow-md"
                >
                  Create Coupon
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
export default PlatformAdminPage;
