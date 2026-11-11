import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, TrendingUp, UtensilsCrossed, Grid,
  Users, CalendarCheck, Receipt, Settings, ChefHat,
  Bell, LogOut, ShieldCheck, ExternalLink, Menu, X, Sparkles, Globe, Star
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const AdminLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile drawer on route navigation
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navLinks = [
    { label: 'Overview & KPIs', path: '/admin/overview', icon: LayoutDashboard },
    { label: 'Sales Analytics', path: '/admin/analytics', icon: TrendingUp },
    { label: 'Menu Management', path: '/admin/menu', icon: UtensilsCrossed },
    { label: 'Floor & Tables', path: '/admin/tables', icon: Grid },
    { label: 'Reservations', path: '/admin/reservations', icon: CalendarCheck },
    { label: 'Billing & Invoices', path: '/admin/billing', icon: Receipt },
    { label: 'Customer Reviews', path: '/admin/feedback', icon: Star },
    { label: 'SaaS Subscription', path: '/admin/subscription', icon: Sparkles },
    { label: 'Staff & Roles', path: '/admin/staff', icon: Users },
    { label: 'Restaurant Settings', path: '/admin/settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-[#090a0f] text-zinc-100 flex flex-col md:flex-row font-sans">
      {/* Mobile Top Header */}
      <header className="md:hidden h-14 bg-[#12131a] border-b border-zinc-800/80 px-4 flex items-center justify-between sticky top-0 z-50">
        <Link to="/admin/overview" className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-brand-600 to-amber-500 flex items-center justify-center shadow-md shadow-brand-500/20">
            <ShieldCheck className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="font-bold text-xs tracking-tight text-white block">
              The Royal Saffron
            </span>
            <span className="text-[10px] font-medium text-amber-400 block leading-none">
              Admin Portal
            </span>
          </div>
        </Link>

        <div className="flex items-center space-x-2">
          <Link
            to="/menu"
            target="_blank"
            className="p-2 rounded-lg bg-zinc-800/80 text-zinc-300 text-xs border border-zinc-700/50"
            title="Customer View"
          >
            <ExternalLink className="w-4 h-4" />
          </Link>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-lg bg-zinc-800 text-zinc-200 border border-zinc-700 transition"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5 text-amber-400" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </header>

      {/* Mobile Menu Dropdown / Overlay */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-x-0 top-14 bottom-0 z-40 bg-black/80 backdrop-blur-md flex flex-col animate-fade-in">
          <div className="bg-[#12131a] border-b border-zinc-800 p-4 max-h-[85vh] overflow-y-auto flex flex-col justify-between flex-1">
            <div className="space-y-4">
              {/* Gateways */}
              <div className="p-3 bg-zinc-900/80 rounded-2xl border border-zinc-800/80 space-y-2">
                <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block">
                  Operations Gateways
                </span>
                <div className="grid grid-cols-2 gap-2">
                  <Link
                    to="/kitchen"
                    className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-zinc-800/80 text-zinc-200 text-xs font-semibold border border-zinc-700/60"
                  >
                    <ChefHat className="w-4 h-4 text-amber-400" />
                    <span>Kitchen KDS</span>
                  </Link>
                  <Link
                    to="/staff"
                    className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-zinc-800/80 text-zinc-200 text-xs font-semibold border border-zinc-700/60"
                  >
                    <Bell className="w-4 h-4 text-brand-400" />
                    <span>Staff Portal</span>
                  </Link>
                </div>
                {user?.role === 'PLATFORM_SUPER_ADMIN' && (
                  <Link
                    to="/platform"
                    className="flex items-center justify-center space-x-2 px-3 py-2 rounded-xl bg-amber-500/15 text-amber-300 text-xs font-bold border border-amber-500/30"
                  >
                    <Globe className="w-4 h-4 text-amber-400" />
                    <span>Platform Super Admin</span>
                  </Link>
                )}
              </div>

              {/* Navigation Links */}
              <nav className="space-y-1">
                {navLinks.map((item) => {
                  const isActive = location.pathname === item.path;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.label}
                      to={item.path}
                      className={`flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
                        isActive
                          ? 'bg-brand-500/15 text-brand-400 border border-brand-500/30'
                          : 'text-zinc-300 hover:bg-zinc-800/60'
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${isActive ? 'text-brand-400' : 'text-zinc-400'}`} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>

            {/* User Info & Logout on Mobile */}
            <div className="pt-4 mt-4 border-t border-zinc-800 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-full bg-brand-500/20 text-brand-400 border border-brand-500/30 flex items-center justify-center font-bold text-xs">
                  {user?.full_name?.charAt(0) || 'A'}
                </div>
                <div>
                  <span className="text-xs font-semibold text-zinc-200 block truncate max-w-[160px]">
                    {user?.full_name || 'Administrator'}
                  </span>
                  <span className="text-[10px] text-zinc-400 uppercase font-medium">
                    {user?.role || 'ADMIN'}
                  </span>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-semibold flex items-center space-x-1.5 border border-red-500/30"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:w-64 bg-[#12131a] border-r border-zinc-800/80 flex-col flex-shrink-0">
        <div className="p-4 border-b border-zinc-800/80 flex items-center justify-between">
          <Link to="/admin/overview" className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-amber-500 flex items-center justify-center shadow-lg shadow-brand-500/20">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-sm tracking-tight text-white block">
                The Royal Saffron
              </span>
              <span className="text-[11px] font-medium text-amber-400 block">
                Admin Control Center
              </span>
            </div>
          </Link>
        </div>

        {/* Quick Portal Switcher */}
        <div className="p-3 bg-zinc-900/60 border-b border-zinc-800/60 flex flex-col space-y-1.5">
          <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider px-2">
            Operations Gateways
          </span>
          <div className="grid grid-cols-2 gap-1.5">
            <Link
              to="/kitchen"
              className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300 hover:text-white text-xs border border-zinc-700/40 transition"
            >
              <ChefHat className="w-3.5 h-3.5 text-amber-400" />
              <span>Kitchen</span>
            </Link>
            <Link
              to="/staff"
              className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800/60 hover:bg-zinc-800 text-zinc-300 hover:text-white text-xs border border-zinc-700/40 transition"
            >
              <Bell className="w-3.5 h-3.5 text-brand-400" />
              <span>Staff / Floor</span>
            </Link>
          </div>
          {user?.role === 'PLATFORM_SUPER_ADMIN' && (
            <Link
              to="/platform"
              className="flex items-center justify-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-xs border border-amber-500/30 transition font-bold"
            >
              <Globe className="w-3.5 h-3.5 text-amber-400" />
              <span>Platform Super Admin</span>
            </Link>
          )}
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navLinks.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.label}
                to={item.path}
                className={`flex items-center space-x-3 px-3 py-2.5 rounded-xl text-xs font-medium transition ${
                  isActive
                    ? 'bg-brand-500/15 text-brand-400 border border-brand-500/30'
                    : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-brand-400' : 'text-zinc-400'}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Info & Logout */}
        <div className="p-3 border-t border-zinc-800/80 bg-zinc-900/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-full bg-brand-500/20 text-brand-400 border border-brand-500/30 flex items-center justify-center font-bold text-xs">
                {user?.full_name?.charAt(0) || 'A'}
              </div>
              <div className="overflow-hidden">
                <span className="text-xs font-semibold text-zinc-200 block truncate">
                  {user?.full_name || 'Administrator'}
                </span>
                <span className="text-[10px] text-zinc-400 block uppercase font-medium">
                  {user?.role || 'ADMIN'}
                </span>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="hidden md:flex h-14 border-b border-zinc-800/80 bg-[#12131a]/80 backdrop-blur-md px-6 items-center justify-between">
          <div className="flex items-center space-x-3">
            <h1 className="text-sm font-semibold text-zinc-200">
              {navLinks.find((l) => l.path === location.pathname)?.label || 'Administration'}
            </h1>
          </div>

          <div className="flex items-center space-x-3">
            <Link
              to="/menu"
              target="_blank"
              className="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-zinc-800/70 hover:bg-zinc-800 text-xs font-medium text-zinc-300 hover:text-white border border-zinc-700/50 transition"
            >
              <span>Customer App View</span>
              <ExternalLink className="w-3 h-3 text-zinc-400" />
            </Link>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
