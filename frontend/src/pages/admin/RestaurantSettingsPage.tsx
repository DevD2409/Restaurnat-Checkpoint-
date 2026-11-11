import React, { useState, useEffect } from 'react';
import { 
  Settings, Save, CheckCircle2, Shield, Wifi, Percent, Clock, 
  Palette, CreditCard, Sparkles, Building2, Store, Lock, Layers
} from 'lucide-react';
import { restaurantApi } from '../../services/api';
import { Restaurant } from '../../types';

export const RestaurantSettingsPage: React.FC = () => {
  const [profile, setProfile] = useState<Restaurant | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<'profile' | 'branding' | 'billing' | 'facilities' | 'gateway'>('profile');

  // Form states
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [tagline, setTagline] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [gstNumber, setGstNumber] = useState('');
  const [taxPercentage, setTaxPercentage] = useState(5.0);
  const [serviceChargePercentage, setServiceChargePercentage] = useState(5.0);
  const [currency, setCurrency] = useState('INR');
  const [currencySymbol, setCurrencySymbol] = useState('₹');
  const [logoUrl, setLogoUrl] = useState('');
  const [primaryColor, setPrimaryColor] = useState('#f97316');
  const [facilities, setFacilities] = useState('High-Speed Wi-Fi, Valet Parking, Wheelchair Accessible, Air Conditioned, Live Music, Outdoor Seating');
  const [serviceTypes, setServiceTypes] = useState('DINE_IN,TAKEAWAY,ROOM_SERVICE,DELIVERY');
  const [razorpayKeyId, setRazorpayKeyId] = useState('');
  const [wifiSsid, setWifiSsid] = useState('');
  const [wifiPassword, setWifiPassword] = useState('');
  const [wifiInstructions, setWifiInstructions] = useState('');
  const [openingTime, setOpeningTime] = useState('11:30 AM');
  const [closingTime, setClosingTime] = useState('11:30 PM');

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await restaurantApi.getProfile();
        setProfile(data);
        setName(data.name);
        setSlug(data.slug || '');
        setTagline(data.tagline || '');
        setAddress(data.address || '');
        setPhone(data.phone || '');
        setEmail(data.email || '');
        setGstNumber(data.gst_number || '');
        setTaxPercentage(data.tax_percentage);
        setServiceChargePercentage(data.service_charge_percentage);
        setCurrency(data.currency || 'INR');
        setCurrencySymbol(data.currency_symbol || '₹');
        setLogoUrl(data.logo_url || '');
        setPrimaryColor(data.primary_color || '#f97316');
        setFacilities(data.facilities || 'High-Speed Wi-Fi, Valet Parking, Air Conditioned');
        setServiceTypes(data.service_types || 'DINE_IN,TAKEAWAY,ROOM_SERVICE,DELIVERY');
        setRazorpayKeyId(data.razorpay_key_id || '');
        setWifiSsid(data.wifi_ssid || '');
        setWifiPassword(data.wifi_password || '');
        setWifiInstructions(data.wifi_instructions || '');
        setOpeningTime(data.opening_time || '11:30 AM');
        setClosingTime(data.closing_time || '11:30 PM');
      } catch (err) {
        console.error('Failed to load settings:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);

    try {
      const updated = await restaurantApi.updateProfile({
        name,
        slug,
        tagline,
        address,
        phone,
        email,
        gst_number: gstNumber,
        tax_percentage: taxPercentage,
        service_charge_percentage: serviceChargePercentage,
        currency,
        currency_symbol: currencySymbol,
        logo_url: logoUrl,
        primary_color: primaryColor,
        facilities,
        service_types: serviceTypes,
        razorpay_key_id: razorpayKeyId,
        wifi_ssid: wifiSsid,
        wifi_password: wifiPassword,
        wifi_instructions: wifiInstructions,
        opening_time: openingTime,
        closing_time: closingTime,
      });
      setProfile(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      alert('Failed to update restaurant settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !profile) {
    return (
      <div className="py-20 text-center animate-fade-in">
        <div className="w-10 h-10 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-xs text-zinc-400">Loading restaurant configuration...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-xl font-bold text-white">{profile.name}</h2>
            <span className="px-2.5 py-0.5 bg-orange-500/10 border border-orange-500/30 text-orange-400 text-xs font-semibold rounded-full">
              {profile.subscription_plan || 'PRO'} Tenant
            </span>
          </div>
          <p className="text-xs text-zinc-400">
            Self-service portal: branding, multi-tenant web slug, payment gateways, and dining options.
          </p>
        </div>

        {savedSuccess && (
          <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-bold animate-fade-in">
            <CheckCircle2 className="w-4 h-4" />
            <span>Configuration Saved!</span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2 overflow-x-auto text-xs font-semibold">
        {[
          { id: 'profile', label: 'General & Slug', icon: Store },
          { id: 'branding', label: 'Branding & Theme', icon: Palette },
          { id: 'billing', label: 'Taxes & Currency', icon: Percent },
          { id: 'facilities', label: 'Facilities & Wi-Fi', icon: Wifi },
          { id: 'gateway', label: 'Payment Gateway', icon: CreditCard },
        ].map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id as any)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-xl transition-all ${
                activeTab === t.id 
                  ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/20' 
                  : 'bg-zinc-900/80 text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      <form onSubmit={handleSave} className="space-y-6 text-xs">
        {/* Profile Details Tab */}
        {activeTab === 'profile' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-white border-b border-zinc-800 pb-2 flex items-center gap-2">
              <Store className="w-4 h-4 text-orange-400" />
              Profile & Tenant URL
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Restaurant Name *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Tenant Web Slug *
                </label>
                <div className="relative">
                  <span className="text-[11px] font-mono text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2">
                    /
                  </span>
                  <input
                    type="text"
                    required
                    value={slug}
                    onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                    className="w-full pl-6 pr-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 font-mono text-amber-400 focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Culinary Tagline
              </label>
              <input
                type="text"
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Physical Address
              </label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Official Contact Phone
                </label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Contact Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Branding Tab */}
        {activeTab === 'branding' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-white border-b border-zinc-800 pb-2 flex items-center gap-2">
              <Palette className="w-4 h-4 text-orange-400" />
              Custom Theme & Visual Identity
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Primary Brand Accent Color
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-10 h-10 rounded-lg cursor-pointer bg-transparent border-0"
                  />
                  <input
                    type="text"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white font-mono uppercase"
                  />
                </div>
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Restaurant Logo Image URL
                </label>
                <input
                  type="text"
                  placeholder="https://images.example.com/logo.png"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Taxes & Charges Tab */}
        {activeTab === 'billing' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-white border-b border-zinc-800 pb-2 flex items-center gap-2">
              <Percent className="w-4 h-4 text-orange-400" />
              Taxation, GST & Currency Configuration
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  GST Tax Percentage (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="30"
                  required
                  value={taxPercentage}
                  onChange={(e) => setTaxPercentage(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Service Charge (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="20"
                  required
                  value={serviceChargePercentage}
                  onChange={(e) => setServiceChargePercentage(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  GSTIN / Tax Registration ID
                </label>
                <input
                  type="text"
                  value={gstNumber}
                  onChange={(e) => setGstNumber(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white font-mono uppercase focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Facilities & Wi-Fi Tab */}
        {activeTab === 'facilities' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-white border-b border-zinc-800 pb-2 flex items-center gap-2">
              <Wifi className="w-4 h-4 text-orange-400" />
              Facilities & Guest Wi-Fi Portal
            </h3>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Available Guest Amenities & Facilities
              </label>
              <input
                type="text"
                value={facilities}
                onChange={(e) => setFacilities(e.target.value)}
                placeholder="High-Speed Wi-Fi, Valet Parking, Wheelchair Accessible, Air Conditioned"
                className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Guest Wi-Fi SSID
                </label>
                <input
                  type="text"
                  value={wifiSsid}
                  onChange={(e) => setWifiSsid(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Guest Wi-Fi Password
                </label>
                <input
                  type="text"
                  value={wifiPassword}
                  onChange={(e) => setWifiPassword(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-white font-mono focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Payment Gateway Tab */}
        {activeTab === 'gateway' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-white border-b border-zinc-800 pb-2 flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-orange-400" />
              Tenant Merchant Payment Gateway (Razorpay)
            </h3>
            <p className="text-xs text-zinc-400">
              Link your restaurant's individual Razorpay merchant account so guest dining payments settle directly to your bank account.
            </p>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Razorpay Key ID (Key ID)
              </label>
              <input
                type="text"
                placeholder="rzp_live_xxxxxxxxxxxxxx"
                value={razorpayKeyId}
                onChange={(e) => setRazorpayKeyId(e.target.value)}
                className="w-full px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 font-mono text-white focus:outline-none focus:border-orange-500"
              />
              <p className="text-[10px] text-zinc-500 mt-1">Found in your Razorpay Dashboard &rarr; Settings &rarr; API Keys.</p>
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white font-bold text-xs shadow-lg shadow-orange-500/25 flex items-center justify-center space-x-1.5 transition active:scale-[0.99] disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          <span>{saving ? 'Updating Configuration...' : 'Save Configuration Changes'}</span>
        </button>
      </form>
    </div>
  );
};
export default RestaurantSettingsPage;
