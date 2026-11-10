import React, { useState, useEffect } from 'react';
import { 
  Building2, Users, DollarSign, ShoppingBag, ShieldCheck, 
  ExternalLink, CheckCircle2, AlertTriangle, RefreshCw, 
  Search, Filter, ChevronRight, Crown, Power, BarChart3, ArrowUpRight
} from 'lucide-react';
import axios from 'axios';
import { PlatformStats, PlatformTenant } from '../../types';

export function PlatformAdminPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [tenants, setTenants] = useState<PlatformTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const fetchPlatformData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const authHeader = { headers: { Authorization: `Bearer ${token}` } };

      const [statsRes, tenantsRes] = await Promise.all([
        axios.get('/api/v1/platform/stats', authHeader),
        axios.get('/api/v1/platform/restaurants', authHeader)
      ]);

      setStats(statsRes.data);
      setTenants(tenantsRes.data);
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
      const token = localStorage.getItem('token');
      await axios.patch(
        `/api/v1/platform/restaurants/${tenantId}/subscription`,
        { subscription_status: newStatus },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await fetchPlatformData();
    } catch (err) {
      console.error('Failed to update tenant status:', err);
      alert('Failed to update subscription status.');
    } finally {
      setActionLoading(null);
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
    <div className="min-h-screen bg-[#090a0f] text-slate-100 p-6 md:p-10">
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
            Hospitality Platform Directory
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Global monitoring, tenant onboarding, subscription status, and cross-restaurant metrics.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchPlatformData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm font-medium transition-colors"
          >
            <RefreshCw className={`w-4 h-4 text-slate-300 ${loading ? 'animate-spin' : ''}`} />
            Refresh Data
          </button>
          <a
            href="/onboard"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white font-medium text-sm rounded-lg shadow-lg shadow-orange-500/20 transition-all"
          >
            <Building2 className="w-4 h-4" />
            Onboard New Tenant
            <ArrowUpRight className="w-3.5 h-3.5 opacity-80" />
          </a>
        </div>
      </div>

      <div className="max-w-7xl mx-auto space-y-8">
        {/* KPI Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Tenants</span>
              <div className="w-9 h-9 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400">
                <Building2 className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white">
                {stats?.total_tenants ?? tenants.length}
              </span>
              <span className="text-xs text-emerald-400 font-medium">
                {stats?.active_tenants ?? tenants.filter(t => t.subscription_status === 'ACTIVE').length} Active
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">Multi-tenant hospitality brands</p>
          </div>

          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Platform Revenue</span>
              <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <DollarSign className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white">
                ₹{stats?.total_platform_revenue ? stats.total_platform_revenue.toLocaleString('en-IN') : '0'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">Processed guest dining transactions</p>
          </div>

          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Platform Orders</span>
              <div className="w-9 h-9 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
                <ShoppingBag className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white">
                {stats?.total_platform_orders ?? 0}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">Across all restaurants & branches</p>
          </div>

          <div className="bg-[#12141c] border border-slate-800/80 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Registered Staff & Admins</span>
              <div className="w-9 h-9 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                <Users className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white">
                {stats?.total_registered_users ?? 0}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">Owners, managers, chefs, & waiters</p>
          </div>
        </div>

        {/* Tenant Filter and Directory */}
        <div className="bg-[#12141c] border border-slate-800 rounded-xl overflow-hidden shadow-lg">
          <div className="p-5 border-b border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-white">Active Tenants & Hospitality Outlets</h2>
              <span className="px-2.5 py-0.5 bg-slate-800 text-slate-400 rounded-full text-xs font-semibold">
                {filteredTenants.length}
              </span>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-3">
              <div className="relative w-full sm:w-64">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search name, slug, email..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-slate-900 border border-slate-700/80 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors"
                />
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <Filter className="w-4 h-4 text-slate-400" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-700/80 text-slate-200 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-orange-500"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="ACTIVE">Active</option>
                  <option value="SUSPENDED">Suspended</option>
                </select>
              </div>
            </div>
          </div>

          {/* Tenants Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-[#181a24] text-xs uppercase text-slate-400 tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Restaurant / Outlet</th>
                  <th className="py-3 px-4">Slug Identifier</th>
                  <th className="py-3 px-4">Subscription Plan</th>
                  <th className="py-3 px-4">Account Status</th>
                  <th className="py-3 px-4 text-center">Tables</th>
                  <th className="py-3 px-4 text-center">Orders</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {filteredTenants.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-slate-500">
                      No matching tenant restaurants found.
                    </td>
                  </tr>
                ) : (
                  filteredTenants.map((tenant) => (
                    <tr key={tenant.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-4 px-4">
                        <div className="font-semibold text-white">{tenant.name}</div>
                        <div className="text-xs text-slate-400">{tenant.owner_email || 'Owner not listed'}</div>
                      </td>
                      <td className="py-4 px-4">
                        <span className="font-mono text-xs px-2 py-1 bg-slate-900 border border-slate-800 rounded text-amber-400">
                          /{tenant.slug}
                        </span>
                      </td>
                      <td className="py-4 px-4">
                        <span className={`px-2.5 py-1 text-xs font-semibold rounded-full uppercase tracking-wider ${
                          tenant.subscription_plan === 'ENTERPRISE' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/30' :
                          tenant.subscription_plan === 'PRO' ? 'bg-orange-500/10 text-orange-400 border border-orange-500/30' :
                          'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                        }`}>
                          {tenant.subscription_plan}
                        </span>
                      </td>
                      <td className="py-4 px-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full ${
                          tenant.subscription_status === 'ACTIVE' 
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' 
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${tenant.subscription_status === 'ACTIVE' ? 'bg-emerald-400' : 'bg-rose-400'}`} />
                          {tenant.subscription_status}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-center font-semibold text-slate-200">
                        {tenant.total_tables}
                      </td>
                      <td className="py-4 px-4 text-center font-semibold text-slate-200">
                        {tenant.total_orders}
                      </td>
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
      </div>
    </div>
  );
}
export default PlatformAdminPage;
