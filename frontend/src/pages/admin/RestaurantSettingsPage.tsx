import React, { useState, useEffect } from 'react';
import { Settings, Save, CheckCircle2, Shield, Wifi, Percent, Clock } from 'lucide-react';
import { restaurantApi } from '../../services/api';
import { Restaurant } from '../../types';

export const RestaurantSettingsPage: React.FC = () => {
  const [profile, setProfile] = useState<Restaurant | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Form states
  const [name, setName] = useState('');
  const [tagline, setTagline] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [gstNumber, setGstNumber] = useState('');
  const [taxPercentage, setTaxPercentage] = useState(5.0);
  const [serviceChargePercentage, setServiceChargePercentage] = useState(5.0);
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
        setTagline(data.tagline || '');
        setAddress(data.address || '');
        setPhone(data.phone || '');
        setEmail(data.email || '');
        setGstNumber(data.gst_number || '');
        setTaxPercentage(data.tax_percentage);
        setServiceChargePercentage(data.service_charge_percentage);
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
        tagline,
        address,
        phone,
        email,
        gst_number: gstNumber,
        tax_percentage: taxPercentage,
        service_charge_percentage: serviceChargePercentage,
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
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-xs text-zinc-400">Loading restaurant configuration...</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
        <div>
          <h2 className="text-xl font-bold text-white">Restaurant Configuration & Policies</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Manage legal profile, taxes, Wi-Fi credentials, and operating parameters
          </p>
        </div>

        {savedSuccess && (
          <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
            <CheckCircle2 className="w-4 h-4" />
            <span>Settings Saved!</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6 text-xs">
        {/* Profile Details Card */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white border-b border-zinc-800 pb-2">
            Establishment Profile
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Restaurant Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Brand Tagline
              </label>
              <input
                type="text"
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
              Physical Address
            </label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Official Contact Phone
              </label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
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
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                GSTIN Tax ID
              </label>
              <input
                type="text"
                value={gstNumber}
                onChange={(e) => setGstNumber(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white font-mono"
              />
            </div>
          </div>
        </div>

        {/* Taxes & Charges Card */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white border-b border-zinc-800 pb-2">
            Taxation & Charges
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Service Charge Percentage (%)
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="20"
                required
                value={serviceChargePercentage}
                onChange={(e) => setServiceChargePercentage(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
              />
            </div>
          </div>
        </div>

        {/* Guest Wi-Fi Card */}
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white border-b border-zinc-800 pb-2">
            Guest Wi-Fi Configuration
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Wi-Fi Network SSID
              </label>
              <input
                type="text"
                value={wifiSsid}
                onChange={(e) => setWifiSsid(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Wi-Fi Password
              </label>
              <input
                type="text"
                value={wifiPassword}
                onChange={(e) => setWifiPassword(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
              Guest Instructions
            </label>
            <textarea
              rows={2}
              value={wifiInstructions}
              onChange={(e) => setWifiInstructions(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
            ></textarea>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full py-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 flex items-center justify-center space-x-1.5 transition active:scale-[0.99]"
        >
          <Save className="w-4 h-4" />
          <span>{saving ? 'Updating Settings...' : 'Save Configuration Changes'}</span>
        </button>
      </form>
    </div>
  );
};

