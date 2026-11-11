import React, { useState } from 'react';
import { 
  Building2, CheckCircle2, ArrowRight, ArrowLeft, ShieldCheck, 
  Sparkles, Utensils, QrCode, Lock, Mail, Phone, MapPin, 
  Check, AlertCircle, Loader2, DollarSign, Store
} from 'lucide-react';
import { apiClient } from '../../services/api';
import { useNavigate } from 'react-router-dom';

export function OnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [slugChecking, setSlugChecking] = useState(false);
  const [slugAvailable, setSlugAvailable] = useState<boolean | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  // Form State
  const [formData, setFormData] = useState({
    restaurant_name: '',
    slug: '',
    tagline: 'Authentic Flavors & Smart Dining',
    address: '',
    phone: '',
    email: '',
    gst_number: '',
    tax_percentage: 5.0,
    service_charge_percentage: 5.0,
    currency: 'INR',
    currency_symbol: '₹',
    table_count: 8,
    subscription_plan: 'PRO',
    owner_full_name: '',
    owner_email: '',
    owner_username: '',
    owner_password: '',
    owner_phone: ''
  });

  const [onboardedResult, setOnboardedResult] = useState<any>(null);

  const checkSlugAvailability = async (slugToTest: string) => {
    if (!slugToTest || slugToTest.trim().length < 3) {
      setSlugAvailable(null);
      return;
    }
    try {
      setSlugChecking(true);
      const res = await apiClient.get(`/onboarding/check-slug?slug=${encodeURIComponent(slugToTest)}`);
      setSlugAvailable(res.data.available);
    } catch (e) {
      console.error('Slug check failed:', e);
    } finally {
      setSlugChecking(false);
    }
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    const generatedSlug = val.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
    setFormData(prev => ({
      ...prev,
      restaurant_name: val,
      slug: generatedSlug
    }));
    checkSlugAvailability(generatedSlug);
  };

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setFormData(prev => ({ ...prev, slug: val }));
    checkSlugAvailability(val);
  };

  const handleFinalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSubmitting(true);

    try {
      const res = await apiClient.post('/onboarding/register', formData);
      setOnboardedResult(res.data);
      setStep(4); // Success step
    } catch (err: any) {
      console.error('Onboarding failed:', err);
      setErrorMsg(err.response?.data?.detail || 'Registration failed. Please check your inputs.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090a0f] text-slate-100 flex flex-col justify-between p-4 md:p-8">
      {/* Top Navbar */}
      <div className="max-w-4xl mx-auto w-full flex items-center justify-between py-4 border-b border-slate-800/80 mb-6">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-orange-500 to-amber-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
            <Store className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight text-white">Smart Restaurant SaaS</span>
        </div>
        <a 
          href="/login" 
          className="text-xs font-medium text-slate-400 hover:text-orange-400 transition-colors"
        >
          Already have an account? Log in &rarr;
        </a>
      </div>

      {/* Main Container */}
      <div className="max-w-2xl mx-auto w-full bg-[#12141c] border border-slate-800/90 rounded-2xl p-6 md:p-10 shadow-2xl shadow-black/80">
        {/* Step Progress Indicator */}
        <div className="flex items-center justify-between mb-8 pb-4 border-b border-slate-800">
          {[
            { num: 1, title: 'Restaurant Details' },
            { num: 2, title: 'Dining & Tables' },
            { num: 3, title: 'Owner Account' },
            { num: 4, title: 'Activation' },
          ].map((item) => (
            <div key={item.num} className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                step > item.num 
                  ? 'bg-emerald-500 text-white' 
                  : step === item.num 
                  ? 'bg-orange-500 text-white ring-4 ring-orange-500/20' 
                  : 'bg-slate-800 text-slate-500'
              }`}>
                {step > item.num ? <Check className="w-4 h-4" /> : item.num}
              </div>
              <span className={`hidden sm:inline text-xs font-medium ${step >= item.num ? 'text-slate-200' : 'text-slate-500'}`}>
                {item.title}
              </span>
            </div>
          ))}
        </div>

        {errorMsg && (
          <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center gap-3 text-rose-400 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* STEP 1: Restaurant Profile */}
        {step === 1 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-white">Tell us about your restaurant or hotel</h2>
              <p className="text-xs text-slate-400 mt-1">This will be displayed on your digital menus and customer invoices.</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Restaurant / Brand Name *
              </label>
              <div className="relative">
                <Building2 className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  placeholder="e.g., The Heritage Bistro & Lounge"
                  value={formData.restaurant_name}
                  onChange={handleNameChange}
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Unique Slug / Web Identifier *
              </label>
              <div className="relative">
                <span className="text-xs font-mono text-slate-500 absolute left-3 top-1/2 -translate-y-1/2">
                  app.srmp.com/
                </span>
                <input
                  type="text"
                  required
                  placeholder="heritage-bistro"
                  value={formData.slug}
                  onChange={handleSlugChange}
                  className="w-full pl-28 pr-10 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm font-mono text-amber-400 focus:outline-none focus:border-orange-500 transition-colors"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  {slugChecking ? (
                    <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
                  ) : slugAvailable === true ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : slugAvailable === false ? (
                    <AlertCircle className="w-4 h-4 text-rose-400" />
                  ) : null}
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {slugAvailable === true && <span className="text-emerald-400">Slug is available!</span>}
                {slugAvailable === false && <span className="text-rose-400">Slug is already taken. Please customize.</span>}
                {slugAvailable === null && 'Your guests will access your digital QR menu using this URL slug.'}
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Tagline or Culinary Theme
              </label>
              <input
                type="text"
                placeholder="Contemporary Artisanal Cuisine & Mixology"
                value={formData.tagline}
                onChange={e => setFormData({ ...formData, tagline: e.target.value })}
                className="w-full px-3 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-orange-500"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Phone Number
                </label>
                <div className="relative">
                  <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="+91 98765 43210"
                    value={formData.phone}
                    onChange={e => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  GSTIN / Tax ID
                </label>
                <input
                  type="text"
                  placeholder="07AABCR9603R1ZM"
                  value={formData.gst_number}
                  onChange={e => setFormData({ ...formData, gst_number: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500 uppercase"
                />
              </div>
            </div>

            <div className="pt-4 flex justify-end">
              <button
                type="button"
                disabled={!formData.restaurant_name || slugAvailable === false}
                onClick={() => setStep(2)}
                className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 disabled:opacity-50 text-white font-semibold text-sm rounded-xl shadow-lg transition-all"
              >
                Continue to Dining Config
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Dining & Tax Settings */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-white">Floor Plan & Billing Settings</h2>
              <p className="text-xs text-slate-400 mt-1">Configure your physical tables and local tax percentages.</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Number of Initial Tables to Bootstrap
              </label>
              <div className="relative">
                <QrCode className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={formData.table_count}
                  onChange={e => setFormData({ ...formData, table_count: parseInt(e.target.value) || 6 })}
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500"
                />
              </div>
              <p className="text-xs text-slate-500 mt-1">We will automatically generate cryptographic signed QR codes for each table.</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  GST / Tax Percentage (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.tax_percentage}
                  onChange={e => setFormData({ ...formData, tax_percentage: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Service Charge (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.service_charge_percentage}
                  onChange={e => setFormData({ ...formData, service_charge_percentage: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Subscription Tier
              </label>
              <div className="grid grid-cols-3 gap-3">
                {['STARTER', 'PRO', 'ENTERPRISE'].map((plan) => (
                  <button
                    key={plan}
                    type="button"
                    onClick={() => setFormData({ ...formData, subscription_plan: plan })}
                    className={`py-3 px-2 rounded-xl border text-xs font-bold transition-all text-center ${
                      formData.subscription_plan === plan 
                        ? 'bg-orange-500/20 border-orange-500 text-orange-400 ring-2 ring-orange-500/30' 
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    {plan}
                  </button>
                ))}
              </div>
            </div>

            <div className="pt-4 flex justify-between">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="flex items-center gap-2 px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-semibold rounded-xl transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
              <button
                type="button"
                onClick={() => setStep(3)}
                className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white font-semibold text-sm rounded-xl shadow-lg transition-all"
              >
                Continue to Owner Account
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Owner Account */}
        {step === 3 && (
          <form onSubmit={handleFinalSubmit} className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-white">Create Restaurant Owner Account</h2>
              <p className="text-xs text-slate-400 mt-1">This will be your administrative master login with complete restaurant control.</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Your Full Name *
              </label>
              <input
                type="text"
                required
                placeholder="Vikram Malhotra"
                value={formData.owner_full_name}
                onChange={e => setFormData({ ...formData, owner_full_name: e.target.value })}
                className="w-full px-3 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Owner Username *
                </label>
                <input
                  type="text"
                  required
                  placeholder="vikram_owner"
                  value={formData.owner_username}
                  onChange={e => setFormData({ ...formData, owner_username: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Work Email *
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    placeholder="vikram@bistro.com"
                    value={formData.owner_email}
                    onChange={e => setFormData({ ...formData, owner_email: e.target.value })}
                    className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Secure Password *
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={formData.owner_password}
                  onChange={e => setFormData({ ...formData, owner_password: e.target.value })}
                  className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-sm text-slate-100 focus:outline-none focus:border-orange-500"
                />
              </div>
            </div>

            <div className="pt-4 flex justify-between">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="flex items-center gap-2 px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-semibold rounded-xl transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex items-center gap-2 px-7 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 disabled:opacity-50 text-white font-semibold text-sm rounded-xl shadow-lg shadow-orange-500/20 transition-all"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Provisioning Tenant...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Activate Restaurant
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* STEP 4: Success & Quick Access */}
        {step === 4 && onboardedResult && (
          <div className="space-y-6 text-center py-4">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 shadow-xl shadow-emerald-500/10">
              <CheckCircle2 className="w-8 h-8" />
            </div>

            <div>
              <h2 className="text-2xl font-bold text-white">
                {onboardedResult.restaurant_name} is Live!
              </h2>
              <p className="text-sm text-slate-400 mt-1">
                Your multi-tenant restaurant space, tables, and credentials are initialized and ready for service.
              </p>
            </div>

            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 text-left space-y-3 font-mono text-xs">
              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400">Public Dining Menu URL:</span>
                <span className="text-amber-400 font-bold">/{onboardedResult.restaurant_slug}/menu</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400">Owner Username:</span>
                <span className="text-white">{onboardedResult.owner_username}</span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-400">Tables Provisioned:</span>
                <span className="text-white">{onboardedResult.table_count || 6} with Signed QR Tokens</span>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 pt-4">
              <a
                href={`/${onboardedResult.restaurant_slug}/menu`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 py-3 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl border border-slate-700 transition-colors"
              >
                Preview Customer Menu &rarr;
              </a>
              <button
                onClick={() => {
                  if (onboardedResult.access_token) {
                    localStorage.setItem('token', onboardedResult.access_token);
                  }
                  navigate('/admin/overview');
                }}
                className="flex-1 py-3 px-4 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 text-white text-sm font-semibold rounded-xl shadow-lg shadow-orange-500/20 transition-all"
              >
                Launch Restaurant Dashboard
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="text-center text-xs text-slate-500 py-4">
        &copy; 2026 Smart Restaurant Management Platform (SRMP) SaaS. All Rights Reserved.
      </div>
    </div>
  );
}
export default OnboardingPage;

