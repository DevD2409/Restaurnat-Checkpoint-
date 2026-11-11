import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation, useParams } from 'react-router-dom';
import {
  Utensils, ShoppingBag, Bell, Wifi, SplitSquareVertical,
  Calendar, CheckCircle2, X
} from 'lucide-react';
import { useCart } from '../context/CartContext';
import { apiClient, serviceRequestApi } from '../services/api';
import { resolveMediaUrl } from '../config/runtime';

export const CustomerLayout: React.FC = () => {
  const { tenantSlug, qrToken } = useParams<{ tenantSlug?: string; qrToken?: string }>();
  const location = useLocation();
  const { totalItemCount, tableNumber, tableId } = useCart();
  const [showServiceModal, setShowServiceModal] = useState(false);
  const [serviceStatusMessage, setServiceStatusMessage] = useState<string | null>(null);
  const [customNote, setCustomNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [restaurantProfile, setRestaurantProfile] = useState<{
    name: string;
    tagline: string;
    logo_url: string | null;
    primary_color: string;
  }>({
    name: 'The Royal Saffron',
    tagline: 'Smart Bistro & Lounge',
    logo_url: null,
    primary_color: '#f97316'
  });

  useEffect(() => {
    const fetchBranding = async () => {
      try {
        if (tenantSlug) {
          const res = await apiClient.get(`/restaurants/by-slug/${tenantSlug}`);
          if (res.data) {
            setRestaurantProfile({
              name: res.data.name || 'Smart Restaurant',
              tagline: res.data.tagline || 'Exquisite Flavors & Hospitality',
              logo_url: res.data.logo_url || null,
              primary_color: res.data.primary_color || '#f97316',
            });
            if (res.data.primary_color) {
              document.documentElement.style.setProperty('--color-brand-500', res.data.primary_color);
            }
          }
        } else {
          const res = await apiClient.get('/restaurants/');
          if (res.data) {
            setRestaurantProfile({
              name: res.data.name,
              tagline: res.data.tagline,
              logo_url: res.data.logo_url,
              primary_color: res.data.primary_color || '#f97316',
            });
          }
        }
      } catch (e) {
        // Fallback default
      }
    };
    fetchBranding();
  }, [tenantSlug]);

  const basePath = tenantSlug
    ? (qrToken ? `/${tenantSlug}/table/${qrToken}` : `/${tenantSlug}/menu`)
    : (qrToken ? `/table/${qrToken}` : '/menu');

  const handleQuickRequest = async (type: 'CALL_WAITER' | 'WATER' | 'CUTLERY' | 'ASSISTANCE' | 'BILL') => {
    if (!tableId) {
      alert('Table session not active. Please scan table QR code.');
      return;
    }
    setIsSubmitting(true);
    try {
      await serviceRequestApi.create({
        table_id: tableId,
        request_type: type,
        customer_notes: customNote.trim() || undefined,
      });
      setServiceStatusMessage(`Your request for ${type.replace('_', ' ')} has been sent to our staff!`);
      setCustomNote('');
      setTimeout(() => {
        setServiceStatusMessage(null);
        setShowServiceModal(false);
      }, 2200);
    } catch (err) {
      alert('Failed to send request. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const navItems = [
    { label: 'Menu', path: basePath, icon: Utensils },
    { label: 'Cart', path: `${basePath}/cart`, icon: ShoppingBag, badge: totalItemCount },
    { label: 'Split Bill', path: `${basePath}/split-bill`, icon: SplitSquareVertical },
    { label: 'Wi-Fi', path: `${basePath}/wifi`, icon: Wifi },
    { label: 'Book Table', path: `${basePath}/reserve`, icon: Calendar },
  ];

  return (
    <div className="min-h-screen bg-[#090a0f] text-zinc-100 flex flex-col font-sans selection:bg-brand-500 selection:text-white pb-24 md:pb-8">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 bg-[#12131a]/95 backdrop-blur-md border-b border-zinc-800/80 px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link to={basePath} className="flex items-center space-x-2.5">
            {restaurantProfile.logo_url ? (
              <img
                src={resolveMediaUrl(restaurantProfile.logo_url)}
                alt={restaurantProfile.name}
                className="w-9 h-9 rounded-xl object-cover shadow-lg border border-zinc-700"
              />
            ) : (
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg transition-colors"
                style={{ backgroundColor: restaurantProfile.primary_color || '#f97316' }}
              >
                <Utensils className="w-5 h-5 text-white" />
              </div>
            )}
            <div>
              <span className="font-bold text-sm sm:text-base tracking-tight text-white block leading-tight">
                {restaurantProfile.name}
              </span>
              <span className="text-[10px] sm:text-[11px] font-medium text-amber-400/90 tracking-wide block">
                {restaurantProfile.tagline}
              </span>
            </div>
          </Link>

          <div className="flex items-center space-x-2">
            {tableNumber && (
              <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-zinc-800/90 border border-zinc-700/60 text-xs font-semibold text-zinc-200">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Table {tableNumber}</span>
              </div>
            )}

            <button
              onClick={() => setShowServiceModal(true)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-zinc-800/90 hover:bg-zinc-750 text-amber-400 hover:text-amber-300 text-xs font-semibold border border-zinc-700/60 transition shadow-sm"
              title="Call Waiter & Service"
            >
              <Bell className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Call Waiter</span>
            </button>

            <Link
              to={`${basePath}/cart`}
              className="relative p-2 rounded-xl bg-zinc-800/90 hover:bg-zinc-700/80 text-zinc-200 border border-zinc-700/60 transition"
              title="View Cart"
            >
              <ShoppingBag className="w-4 h-4 text-brand-400" />
              {totalItemCount > 0 && (
                <span className="absolute -top-1.5 -right-1.5 bg-brand-500 text-white text-[10px] font-extrabold w-5 h-5 rounded-full flex items-center justify-center border-2 border-[#12131a] shadow-md animate-scale">
                  {totalItemCount}
                </span>
              )}
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4">
        <Outlet />
      </main>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 bg-[#12131a]/95 backdrop-blur-xl border-t border-zinc-800/90 md:hidden px-2 py-2 safe-area-pb">
        <div className="flex items-center justify-around max-w-md mx-auto">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.label}
                to={item.path}
                className={`relative flex flex-col items-center py-1 px-2.5 rounded-xl transition ${
                  isActive
                    ? 'text-brand-400 font-bold'
                    : 'text-zinc-400 hover:text-zinc-200 font-normal'
                }`}
              >
                <div className="relative">
                  <Icon className="w-5 h-5" />
                  {item.badge !== undefined && item.badge > 0 && (
                    <span className="absolute -top-1.5 -right-2 bg-brand-500 text-white text-[9px] font-bold px-1.5 py-0.2 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </div>
                <span className="text-[10px] mt-1 tracking-tight">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Call Waiter & Service Request Modal */}
      {showServiceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-[#181924] border border-zinc-700/80 rounded-3xl max-w-md w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setShowServiceModal(false)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-100 p-1.5 rounded-lg bg-zinc-800/60"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center space-x-3 mb-5">
              <div className="w-10 h-10 rounded-2xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
                <Bell className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-base text-white">Guest Service Requests</h3>
                <p className="text-xs text-zinc-400">Directly alerts your assigned floor staff</p>
              </div>
            </div>

            {serviceStatusMessage ? (
              <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center space-x-3 text-emerald-400 text-xs font-semibold">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                <span>{serviceStatusMessage}</span>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    disabled={isSubmitting}
                    onClick={() => handleQuickRequest('CALL_WAITER')}
                    className="p-3.5 rounded-2xl bg-zinc-900/90 hover:bg-brand-500/15 hover:border-brand-500/40 border border-zinc-800 text-left transition flex flex-col items-start active:scale-95"
                  >
                    <span className="text-sm font-bold text-zinc-100">👋 Call Waiter</span>
                    <span className="text-[11px] text-zinc-400 mt-0.5">Assistance at table</span>
                  </button>

                  <button
                    disabled={isSubmitting}
                    onClick={() => handleQuickRequest('WATER')}
                    className="p-3.5 rounded-2xl bg-zinc-900/90 hover:bg-brand-500/15 hover:border-brand-500/40 border border-zinc-800 text-left transition flex flex-col items-start active:scale-95"
                  >
                    <span className="text-sm font-bold text-zinc-100">💧 Request Water</span>
                    <span className="text-[11px] text-zinc-400 mt-0.5">Regular or Bottled</span>
                  </button>

                  <button
                    disabled={isSubmitting}
                    onClick={() => handleQuickRequest('CUTLERY')}
                    className="p-3.5 rounded-2xl bg-zinc-900/90 hover:bg-brand-500/15 hover:border-brand-500/40 border border-zinc-800 text-left transition flex flex-col items-start active:scale-95"
                  >
                    <span className="text-sm font-bold text-zinc-100">🍴 Cutlery</span>
                    <span className="text-[11px] text-zinc-400 mt-0.5">Spoons, forks, plates</span>
                  </button>

                  <button
                    disabled={isSubmitting}
                    onClick={() => handleQuickRequest('BILL')}
                    className="p-3.5 rounded-2xl bg-zinc-900/90 hover:bg-brand-500/15 hover:border-brand-500/40 border border-zinc-800 text-left transition flex flex-col items-start active:scale-95"
                  >
                    <span className="text-sm font-bold text-zinc-100">🧾 Request Bill</span>
                    <span className="text-[11px] text-zinc-400 mt-0.5">Ready to check out</span>
                  </button>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-1.5 text-[10px]">
                    Optional Note for Waiter
                  </label>
                  <input
                    type="text"
                    value={customNote}
                    onChange={(e) => setCustomNote(e.target.value)}
                    placeholder="e.g. Please bring clean glasses or baby chair"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
