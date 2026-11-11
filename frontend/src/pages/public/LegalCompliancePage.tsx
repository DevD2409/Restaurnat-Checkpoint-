import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ShieldCheck,
  FileText,
  RefreshCcw,
  Tag,
  Mail,
  MapPin,
  User,
  ArrowLeft,
  AlertTriangle,
  Phone,
  CheckCircle2,
  Clock,
  AlertCircle,
  Globe,
  Receipt
} from 'lucide-react';
import { subscriptionsApi } from '../../services/api';
import { ComplianceEntityInfo } from '../../types';

export type ComplianceTab = 'terms' | 'privacy' | 'refund' | 'pricing' | 'contact';

interface LegalCompliancePageProps {
  initialTab?: ComplianceTab;
}

const DEFAULT_INDIVIDUAL_ENTITY_INFO: ComplianceEntityInfo = {
  business_operating_model: 'INDIVIDUAL_UNREGISTERED',
  owner_legal_name: undefined,
  is_owner_legal_name_configured: false,
  brand_trade_name: 'SRMP (Smart Restaurant Management Platform)',
  business_identity_status: 'PENDING_OWNER_CONFIGURATION',
  is_business_identity_verified: false,
  pan: undefined,
  is_pan_configured: false,
  business_address: undefined,
  is_address_configured: false,
  is_gst_registered: false,
  gstin: undefined,
  is_gstin_verified: false,
  is_gst_rate_ca_confirmed: false,
  gst_rate_percentage: 0,
  supplier_state_code: undefined,
  sac_code: undefined,
  sac_description: undefined,
  is_sac_approved_by_ca: false,
  settlement_account_ref: undefined,
  settlement_bank_name: undefined,
  is_bank_account_verified: false,
  production_domain: undefined,
  is_production_domain_configured: false,
  support_email: undefined,
  is_support_email_configured: false,
  grievance_email: undefined,
  is_grievance_email_configured: false,
  telephone_helpline: undefined,
  is_telephone_configured: false,
  grievance_contact_name: undefined,
  is_grievance_contact_configured: false,
  refund_policy_status: 'DRAFT_PENDING_OWNER_APPROVAL',
  is_refund_policy_approved: false
};

export const LegalCompliancePage: React.FC<LegalCompliancePageProps> = ({ initialTab }) => {
  const location = useLocation();

  const getTabFromPath = (): ComplianceTab => {
    if (initialTab) return initialTab;
    const path = location.pathname.toLowerCase();
    if (path.includes('privacy')) return 'privacy';
    if (path.includes('refund') || path.includes('cancellation')) return 'refund';
    if (path.includes('pricing')) return 'pricing';
    if (path.includes('contact')) return 'contact';
    return 'terms';
  };

  const [activeTab, setActiveTab] = useState<ComplianceTab>(getTabFromPath());
  const [entityInfo, setEntityInfo] = useState<ComplianceEntityInfo>(DEFAULT_INDIVIDUAL_ENTITY_INFO);

  useEffect(() => {
    subscriptionsApi.getComplianceInfo()
      .then((data) => {
        if (data) setEntityInfo(data);
      })
      .catch((err) => {
        console.warn('Could not load dynamic compliance info, using fallback individual-business config:', err);
      });
  }, []);

  const displayOperatorLegalName = entityInfo.owner_legal_name
    ? entityInfo.owner_legal_name
    : 'Platform Owner (Legal Name Pending Configuration)';

  const isGstInvoiceActive = Boolean(entityInfo.is_gst_registered && entityInfo.is_gst_rate_ca_confirmed);

  return (
    <div className="min-h-screen bg-[#090a0f] text-zinc-100 flex flex-col justify-between selection:bg-amber-500 selection:text-black">
      {/* Top Header */}
      <header className="border-b border-zinc-800 bg-[#12131a]/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Link
              to="/menu"
              className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white transition"
              title="Return to Menu"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-xl bg-amber-500 flex items-center justify-center font-black text-black text-xs shadow-lg shadow-amber-500/20">
                SRMP
              </div>
              <div>
                <h1 className="text-sm font-bold text-white tracking-wide">{entityInfo.brand_trade_name}</h1>
                <span className="text-[10px] text-zinc-400 block font-mono">
                  Individual Business SaaS Legal & Compliance
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Link
              to="/login"
              className="px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold border border-zinc-700 transition"
            >
              Staff Portal
            </Link>
            <Link
              to="/onboard"
              className="px-3.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold transition shadow-md shadow-amber-500/10"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-6xl mx-auto w-full px-4 py-8 flex-1">
        {/* Navigation Tabs */}
        <div className="flex items-center space-x-1 border-b border-zinc-800 pb-2 mb-8 overflow-x-auto text-xs font-medium">
          <button
            onClick={() => setActiveTab('terms')}
            className={`px-4 py-2 rounded-xl transition flex items-center space-x-2 whitespace-nowrap ${
              activeTab === 'terms'
                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Terms of Service</span>
          </button>

          <button
            onClick={() => setActiveTab('privacy')}
            className={`px-4 py-2 rounded-xl transition flex items-center space-x-2 whitespace-nowrap ${
              activeTab === 'privacy'
                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Privacy Policy</span>
          </button>

          <button
            onClick={() => setActiveTab('refund')}
            className={`px-4 py-2 rounded-xl transition flex items-center space-x-2 whitespace-nowrap ${
              activeTab === 'refund'
                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
            }`}
          >
            <RefreshCcw className="w-3.5 h-3.5" />
            <span>Refund & Cancellation</span>
          </button>

          <button
            onClick={() => setActiveTab('pricing')}
            className={`px-4 py-2 rounded-xl transition flex items-center space-x-2 whitespace-nowrap ${
              activeTab === 'pricing'
                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
            }`}
          >
            <Tag className="w-3.5 h-3.5" />
            <span>Pricing & Tax Policy</span>
          </button>

          <button
            onClick={() => setActiveTab('contact')}
            className={`px-4 py-2 rounded-xl transition flex items-center space-x-2 whitespace-nowrap ${
              activeTab === 'contact'
                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
            }`}
          >
            <Mail className="w-3.5 h-3.5" />
            <span>Contact & Operator Identity</span>
          </button>
        </div>

        {/* Tab 1: Terms of Service */}
        {activeTab === 'terms' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-6">
            <div>
              <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-zinc-800 text-[11px] font-mono text-zinc-300 mb-2">
                <FileText className="w-3.5 h-3.5 text-amber-400" />
                <span>Operating Model: Individual / Unregistered Business</span>
              </div>
              <h2 className="text-2xl font-bold text-white">Terms and Conditions of Service</h2>
              <p className="text-xs text-zinc-400 mt-1">
                Please read these terms carefully before subscribing to the {entityInfo.brand_trade_name}.
              </p>
            </div>

            <div className="space-y-4 text-xs text-zinc-300 leading-relaxed border-t border-zinc-800 pt-4">
              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">1. Platform Operator & Service Description</h3>
                <p>
                  <strong className="text-white">{entityInfo.brand_trade_name}</strong> (&quot;SRMP&quot;, &quot;Platform&quot;)
                  is operated by an <strong className="text-amber-300">individual business owner</strong>:{' '}
                  <strong className="text-white">{displayOperatorLegalName}</strong>{' '}
                  <span className="text-zinc-400">(Identity Status: {entityInfo.business_identity_status})</span>.
                  SRMP provides digitized restaurant table QR menus, real-time Kitchen Display Systems (KDS), waiter dispatch floor operations,
                  point-of-sale split billing, analytics, and customer dining management tools.
                </p>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">2. Dual-Flow Payment Architecture & Merchant Separation</h3>
                <p>
                  SRMP strictly separates two completely independent payment flows:
                </p>
                <ul className="list-disc pl-5 space-y-1 text-zinc-300">
                  <li>
                    <strong className="text-amber-400">Flow A (Restaurant Customer Dining Payments):</strong> Payments made by dining customers for
                    food and beverage orders at restaurant tables settle directly into the respective independent restaurant&apos;s own Razorpay merchant account.
                    SRMP does not intermediate, hold, or collect restaurant dining funds.
                  </li>
                  <li>
                    <strong className="text-amber-400">Flow B (SaaS Platform Subscriptions):</strong> Direct subscription plan fees —{' '}
                    <strong className="text-white">Monthly — ₹999/month (inclusive of applicable taxes)</strong> and{' '}
                    <strong className="text-white">Yearly — ₹9,999/year (inclusive of applicable taxes)</strong> — paid by restaurant owners
                    settle directly into the platform owner&apos;s verified individual bank account under the Platform Razorpay merchant account.
                  </li>
                </ul>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">3. Multi-Tenant Account Security & Fair Use</h3>
                <p>
                  Each subscribing restaurant (&quot;Tenant&quot;) is issued an isolated workspace governed by strict multi-tenant database constraints.
                  Tenants are solely responsible for safeguarding staff credentials and preventing unauthorized access to their administrative dashboards.
                </p>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">4. Subscription Term, Renewals & 7-Day Grace Protection</h3>
                <p>
                  Subscriptions are billed monthly or annually at tax-inclusive prices with zero compulsory convenience fees added at checkout.
                  When a subscription lapses, SRMP provides a guaranteed <strong className="text-amber-400">7-day operational grace period</strong> during
                  which tables and kitchen displays remain functional, ensuring zero dining disruption during renewals.
                </p>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">5. Governing Law and Dispute Jurisdiction</h3>
                <p>
                  These Terms are governed by and construed in accordance with the laws of India. Any disputes arising out of or related to these terms
                  shall be subject to the competent courts having jurisdiction at the platform owner&apos;s principal place of business in India.
                </p>
              </section>
            </div>
          </div>
        )}

        {/* Tab 2: Privacy Policy */}
        {activeTab === 'privacy' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-6">
            <div>
              <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-zinc-800 text-[11px] font-mono text-zinc-300 mb-2">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>Data Protection & Multi-Tenant Isolation</span>
              </div>
              <h2 className="text-2xl font-bold text-white">Privacy and Data Protection Policy</h2>
              <p className="text-xs text-zinc-400 mt-1">
                How {displayOperatorLegalName} operating {entityInfo.brand_trade_name} protects tenant, restaurant, and customer dining data.
              </p>
            </div>

            <div className="space-y-4 text-xs text-zinc-300 leading-relaxed border-t border-zinc-800 pt-4">
              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">1. Scope of Privacy Protection</h3>
                <p>
                  We respect data privacy under the Digital Personal Data Protection Act (DPDP Act, India) and industry security standards.
                  This policy outlines how data is collected, stored, encrypted, and isolated across our multi-tenant cloud architecture.
                </p>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">2. Strict Multi-Tenant Data Isolation</h3>
                <p>
                  Tenant data is segregated using strict foreign key and query-scope constraints (<code className="text-amber-400">tenant_id</code> / <code className="text-amber-400">restaurant_id</code>).
                  A restaurant owner or staff member cannot view, modify, or export another restaurant&apos;s orders, menus, revenue, or customer details.
                </p>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">3. Information Collected</h3>
                <ul className="list-disc pl-5 space-y-1 text-zinc-300">
                  <li><strong className="text-white">Tenant & Staff Data:</strong> Name, phone number, email address, restaurant physical address, optional GSTIN, staff role permissions.</li>
                  <li><strong className="text-white">Dining Transaction Data:</strong> Table numbers, order items, timestamps, bill amounts, and feedback ratings.</li>
                  <li><strong className="text-white">Zero Sensitive Card Storage:</strong> SRMP <em className="text-amber-400">never</em> stores complete credit/debit card numbers, CVVs, or NetBanking credentials. All payment processing is handled via tokenized checkout through PCI-DSS certified payment gateways.</li>
                </ul>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">4. Secure Media and Asset Storage</h3>
                <p>
                  Menu photos, restaurant logos, and moderated customer feedback pictures are stored in object storage with file validation.
                  Executable and unauthorized file types are strictly blocked.
                </p>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">5. Support & Grievance Contact Information</h3>
                <p>
                  For data subject access requests, deletion requests, or grievances, use the configured platform owner grievance channel:
                </p>
                <div className="p-3.5 bg-zinc-900 rounded-xl border border-zinc-800 text-xs space-y-1.5 font-mono">
                  <div>
                    <strong className="text-zinc-200">Grievance Contact:</strong>{' '}
                    {entityInfo.grievance_contact_name || 'Pending Owner Designation'}
                    {!entityInfo.is_grievance_contact_configured && (
                      <span className="ml-2 text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                        Pending Configuration
                      </span>
                    )}
                  </div>
                  <div>
                    <strong className="text-zinc-200">Email:</strong>{' '}
                    {entityInfo.grievance_email || 'Pending Domain Email Configuration'}
                    {!entityInfo.is_grievance_email_configured && (
                      <span className="ml-2 text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                        Pending Configuration
                      </span>
                    )}
                  </div>
                  <div>
                    <strong className="text-zinc-200">Address:</strong>{' '}
                    {entityInfo.business_address || 'Pending Principal Place of Business Address'}
                    {!entityInfo.is_address_configured && (
                      <span className="ml-2 text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                        Pending Configuration
                      </span>
                    )}
                  </div>
                </div>
              </section>
            </div>
          </div>
        )}

        {/* Tab 3: Refund & Cancellation Policy */}
        {activeTab === 'refund' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-amber-500/15 border border-amber-500/30 text-[11px] font-mono text-amber-300 mb-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  <span>Status: {entityInfo.refund_policy_status}</span>
                </div>
                <h2 className="text-2xl font-bold text-white">Cancellation and Refund Policy</h2>
                <p className="text-xs text-zinc-400 mt-1">
                  Policy framework governing SaaS subscription renewals, cancellations, and dining refunds.
                </p>
              </div>
            </div>

            <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start space-x-3 text-xs text-amber-200">
              <AlertCircle className="w-5 h-5 mt-0.5 text-amber-400 flex-shrink-0" />
              <div>
                <strong className="block font-bold uppercase tracking-wide">
                  Administrative Notice: Policy Selection Under Owner Evaluation
                </strong>
                <span className="block mt-1 leading-relaxed">
                  Per governance and KYC readiness directives, this document remains a draft proposal awaiting explicit platform owner sign-off
                  unless marked approved in platform configuration.
                </span>
              </div>
            </div>

            <div className="space-y-4 text-xs text-zinc-300 leading-relaxed border-t border-zinc-800 pt-4">
              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">1. SaaS Subscription Cancellation</h3>
                <p>
                  Subscribers may cancel their recurring monthly or yearly subscription directly through the
                  <strong className="text-white"> Admin &gt; Subscription</strong> portal. Upon cancellation, the subscription remains
                  active until the end of the current paid billing cycle.
                </p>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">2. SaaS Subscription Refund Framework (Proposed Options)</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                  <div className="p-3.5 bg-zinc-900 border border-zinc-800 rounded-xl space-y-1.5">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400 block">
                      Proposal Option A: 7-Day Money-Back Guarantee
                    </span>
                    <p className="text-[11px] text-zinc-400">
                      If a newly onboarded restaurant is dissatisfied within the first 7 days of initial subscription activation,
                      a 100% full refund is issued back to the original source payment method.
                    </p>
                  </div>

                  <div className="p-3.5 bg-zinc-900 border border-zinc-800 rounded-xl space-y-1.5">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-300 block">
                      Proposal Option B: Non-Refundable Active Cycle
                    </span>
                    <p className="text-[11px] text-zinc-400">
                      Subscriptions are non-refundable once the billing period commences, while workspace access continues
                      unobstructed until the cycle expiration date.
                    </p>
                  </div>
                </div>
              </section>

              <section className="space-y-2">
                <h3 className="text-sm font-semibold text-white">3. Flow A Customer Dining Payment Refunds</h3>
                <ul className="list-disc pl-5 space-y-1 text-zinc-300">
                  <li>
                    Because customer dining payments settle directly into each independent restaurant&apos;s merchant account,
                    refund requests for dining orders are authorized directly by the respective restaurant manager.
                  </li>
                  <li>
                    Approved refunds are executed via that restaurant&apos;s Razorpay merchant integration back to the diner&apos;s
                    original payment method within standard banking settlement timelines (5–7 business days).
                  </li>
                </ul>
              </section>
            </div>
          </div>
        )}

        {/* Tab 4: Pricing & Tax Policy */}
        {activeTab === 'pricing' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-6">
            <div>
              <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-zinc-800 text-[11px] font-mono text-zinc-300 mb-2">
                <Tag className="w-3.5 h-3.5 text-amber-400" />
                <span>Direct Tax-Inclusive Pricing Schedule</span>
              </div>
              <h2 className="text-2xl font-bold text-white">Subscription Plans & Tax Disclosure</h2>
              <p className="text-xs text-zinc-400 mt-1">
                All subscription prices shown below are final and inclusive of applicable taxes and compulsory charges.
                No additional GST or surprise convenience charges are added on top at checkout.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-zinc-800 pt-6">
              {/* Plan 1: Monthly */}
              <div className="p-5 rounded-xl bg-zinc-900 border border-zinc-800 space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider block">Standard Plan</span>
                    <h3 className="text-lg font-bold text-white">Monthly Plan</h3>
                  </div>
                  <span className="text-xs font-mono text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded">MONTHLY</span>
                </div>
                <div className="space-y-1">
                  <div className="text-2xl font-extrabold text-white">
                    ₹999 <span className="text-xs font-normal text-zinc-400">/ month (inclusive of applicable taxes)</span>
                  </div>
                  <div className="text-[11px] font-mono text-zinc-500">Authoritative Settlement Amount: 99,900 integer paise (30 days)</div>
                </div>
                {isGstInvoiceActive ? (
                  <div className="p-3 bg-zinc-800/60 rounded-lg text-xs space-y-1">
                    <div className="flex justify-between text-zinc-300">
                      <span>Taxable Base Value:</span>
                      <span>₹846.61 (84,661 paise)</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Included GST (18%{entityInfo.sac_code ? ` SAC ${entityInfo.sac_code}` : ''}):</span>
                      <span>₹152.39 (15,239 paise)</span>
                    </div>
                    <div className="flex justify-between font-bold text-white pt-1 border-t border-zinc-700">
                      <span>Final Tax-Inclusive Price:</span>
                      <span className="text-amber-400">₹999.00</span>
                    </div>
                  </div>
                ) : (
                  <div className="p-3 bg-zinc-800/60 rounded-lg text-xs space-y-1">
                    <div className="flex justify-between text-zinc-300">
                      <span>Plan Price (Inclusive):</span>
                      <span>₹999.00</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Additional Convenience / GST Added:</span>
                      <span>₹0.00 (Unregistered Individual Business)</span>
                    </div>
                    <div className="flex justify-between font-bold text-white pt-1 border-t border-zinc-700">
                      <span>Total Final Payable:</span>
                      <span className="text-amber-400">₹999.00</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Plan 2: Yearly */}
              <div className="p-5 rounded-xl bg-zinc-900 border border-amber-500/30 space-y-3">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-[11px] font-bold text-orange-400 uppercase tracking-wider block">Best Value · Save ₹1,989 / yr</span>
                    <h3 className="text-lg font-bold text-white">Yearly Plan</h3>
                  </div>
                  <span className="text-xs font-mono text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded">YEARLY</span>
                </div>
                <div className="space-y-1">
                  <div className="text-2xl font-extrabold text-white">
                    ₹9,999 <span className="text-xs font-normal text-zinc-400">/ year (inclusive of applicable taxes)</span>
                  </div>
                  <div className="text-[11px] font-mono text-zinc-500">Authoritative Settlement Amount: 999,900 integer paise (365 days)</div>
                </div>
                {isGstInvoiceActive ? (
                  <div className="p-3 bg-zinc-800/60 rounded-lg text-xs space-y-1">
                    <div className="flex justify-between text-zinc-300">
                      <span>Taxable Base Value:</span>
                      <span>₹8,473.73 (847,373 paise)</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Included GST (18%{entityInfo.sac_code ? ` SAC ${entityInfo.sac_code}` : ''}):</span>
                      <span>₹1,525.27 (152,527 paise)</span>
                    </div>
                    <div className="flex justify-between font-bold text-white pt-1 border-t border-zinc-700">
                      <span>Final Tax-Inclusive Price:</span>
                      <span className="text-amber-400">₹9,999.00</span>
                    </div>
                  </div>
                ) : (
                  <div className="p-3 bg-zinc-800/60 rounded-lg text-xs space-y-1">
                    <div className="flex justify-between text-zinc-300">
                      <span>Plan Price (Inclusive):</span>
                      <span>₹9,999.00</span>
                    </div>
                    <div className="flex justify-between text-zinc-400">
                      <span>Additional Convenience / GST Added:</span>
                      <span>₹0.00 (Unregistered Individual Business)</span>
                    </div>
                    <div className="flex justify-between font-bold text-white pt-1 border-t border-zinc-700">
                      <span>Total Final Payable:</span>
                      <span className="text-amber-400">₹9,999.00</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2 text-xs text-zinc-300">
              <div className="flex items-center space-x-2">
                <Receipt className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-semibold text-white">Billing & Tax Registration Disclosure</h3>
              </div>
              {isGstInvoiceActive ? (
                <p>
                  The platform operator holds a verified GSTIN (<strong className="font-mono text-white">{entityInfo.gstin}</strong>)
                  with Chartered Accountant-confirmed GST treatment ({entityInfo.gst_rate_percentage}%
                  {entityInfo.sac_code ? `, SAC ${entityInfo.sac_code}` : ''}). GST is already included inside the
                  published ₹999/month and ₹9,999/year subscription prices and is broken out cleanly on your Tax Invoice.
                </p>
              ) : (
                <p>
                  <strong className="text-amber-300">Unregistered Individual Business Disclosure:</strong>{' '}
                  The platform operator currently operates as an <strong className="text-white">individual / unregistered business</strong> and
                  is <strong className="text-white">not GST-registered</strong>. Accordingly, GST is <strong className="text-white">not charged or collected</strong>{' '}
                  on subscriptions, and SRMP issues <strong className="text-white">Non-GST Payment Receipts</strong> (<code className="text-amber-400">R&#123;FY&#125;/...</code>)
                  rather than GST tax invoices. Should the operator obtain GST registration in the future, applicable GST will remain absorbed
                  within or governed strictly by verified tax-inclusive compliance configuration.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Tab 5: Contact Us & Operator Identity */}
        {activeTab === 'contact' && (
          <div className="bg-[#12131a] border border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-6">
            <div>
              <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-zinc-800 text-[11px] font-mono text-zinc-300 mb-2">
                <User className="w-3.5 h-3.5 text-amber-400" />
                <span>Operating Model: {entityInfo.business_operating_model}</span>
              </div>
              <h2 className="text-2xl font-bold text-white">Contact & Individual Operator Identity</h2>
              <p className="text-xs text-zinc-400 mt-1">
                Truthful operator identity, bank settlement readiness, domain status, and support channel configuration.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-zinc-800 pt-6 text-xs">
              <div className="space-y-4">
                <div className="p-4 bg-zinc-900 rounded-xl border border-zinc-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                      Individual / Proprietor Identity
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                      {entityInfo.business_identity_status}
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    <div className="flex items-start space-x-2">
                      <User className="w-4 h-4 text-zinc-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="text-zinc-400 text-[11px] block">Owner Legal Name:</span>
                        <strong className="text-white block">{displayOperatorLegalName}</strong>
                        {!entityInfo.is_owner_legal_name_configured && (
                          <span className="inline-block mt-1 text-[9px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30 font-mono">
                            Pending Owner Legal Name
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-start space-x-2">
                      <Tag className="w-4 h-4 text-zinc-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="text-zinc-400 text-[11px] block">Brand / Trade Name:</span>
                        <strong className="text-white">{entityInfo.brand_trade_name}</strong>
                      </div>
                    </div>

                    <div className="flex items-start space-x-2">
                      <MapPin className="w-4 h-4 text-zinc-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <span className="text-zinc-400 text-[11px] block">Principal Place of Business:</span>
                        <span className="text-zinc-200 block">
                          {entityInfo.business_address || 'Pending Configuration by Platform Owner'}
                        </span>
                        {!entityInfo.is_address_configured && (
                          <span className="inline-block mt-1 text-[9px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30 font-mono">
                            Pending Address Configuration
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-start space-x-2">
                      <CheckCircle2 className={`w-4 h-4 mt-0.5 flex-shrink-0 ${entityInfo.is_gst_registered ? 'text-emerald-400' : 'text-zinc-500'}`} />
                      <div>
                        <span className="text-zinc-400 text-[11px] block">GST Registration Status:</span>
                        {entityInfo.is_gst_registered ? (
                          <span className="text-zinc-200 font-mono">
                            Registered — GSTIN: <strong className="text-white">{entityInfo.gstin || 'Configured'}</strong>
                            {!entityInfo.is_gstin_verified && (
                              <span className="ml-1.5 text-[9px] text-amber-400 bg-amber-500/10 px-1 py-0.5 rounded border border-amber-500/30">
                                Verification Pending
                              </span>
                            )}
                          </span>
                        ) : (
                          <span className="text-zinc-300">
                            Not GST Registered (Individual / Unregistered Business Model)
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-zinc-900 rounded-xl border border-zinc-800 space-y-3">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                    Individual Bank Settlement Destination (Flow B)
                  </span>
                  <div className="space-y-1.5 font-mono text-[11px] text-zinc-300">
                    <div>
                      Settlement Account Type: <strong className="text-white">Owner&apos;s Individual Bank Account</strong>
                    </div>
                    <div>
                      Bank Name:{' '}
                      <strong className="text-white">
                        {entityInfo.settlement_bank_name || 'Pending Bank Verification'}
                      </strong>
                    </div>
                    <div>
                      Account Reference:{' '}
                      <strong className="text-amber-400">
                        {entityInfo.settlement_account_ref || 'Pending Verified Bank Reference'}
                      </strong>
                    </div>
                    {!entityInfo.is_bank_account_verified && (
                      <div className="pt-1 text-[10px] text-amber-400 flex items-center space-x-1">
                        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                        <span>Owner individual bank account verification pending prior to live Razorpay activation</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="p-4 bg-zinc-900 rounded-xl border border-zinc-800 space-y-3">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 block">
                    Domain & Support Channels
                  </span>
                  <div className="space-y-2.5">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <Globe className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                        <span className="text-zinc-400 text-[11px]">Production Domain Status:</span>
                      </div>
                      <div className="pl-6">
                        <span className="text-zinc-200 font-mono text-xs">
                          {entityInfo.production_domain || 'Using temporary hosting provider URLs'}
                        </span>
                        {!entityInfo.is_production_domain_configured && (
                          <span className="block text-[10px] text-zinc-400 bg-zinc-800 p-1.5 rounded border border-zinc-700 mt-1">
                            Temporary Cloudflare Pages / Render URLs remain active until a custom domain is configured.
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <Mail className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                        <span className="text-zinc-400 text-[11px]">General & Technical Support:</span>
                      </div>
                      <div className="pl-6">
                        <span className="text-amber-400 font-mono text-xs">
                          {entityInfo.support_email || 'Pending Owner Support Email'}
                        </span>
                        {!entityInfo.is_support_email_configured && (
                          <span className="block text-[10px] text-amber-400 bg-amber-500/10 p-1 rounded border border-amber-500/20 mt-1">
                            Channel Unconfigured: Configure SUPPORT_EMAIL in backend environment
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <Phone className="w-4 h-4 text-zinc-400 flex-shrink-0" />
                        <span className="text-zinc-400 text-[11px]">Helpline Phone:</span>
                      </div>
                      <div className="pl-6">
                        <span className="text-zinc-200 font-mono text-xs">
                          {entityInfo.telephone_helpline || 'Pending Helpline Number'}
                        </span>
                        {!entityInfo.is_telephone_configured && (
                          <span className="block text-[10px] text-amber-400 bg-amber-500/10 p-1 rounded border border-amber-500/20 mt-1">
                            Channel Unconfigured: Configure TELEPHONE_HELPLINE in backend environment
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 pl-6 pt-1 text-[11px] text-zinc-500">
                      <Clock className="w-3.5 h-3.5" />
                      <span>Support hours and SLA finalized prior to live production launch</span>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-zinc-900 rounded-xl border border-zinc-800 space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400 block">
                    Grievance Redressal Contact
                  </span>
                  <div className="text-[11px] text-zinc-300 font-mono space-y-1">
                    <div>
                      Contact: <strong className="text-white">{entityInfo.grievance_contact_name || 'Pending Designation'}</strong>
                      {!entityInfo.is_grievance_contact_configured && (
                        <span className="ml-1.5 text-[9px] text-amber-400 bg-amber-500/10 px-1 py-0.5 rounded border border-amber-500/20">
                          Pending
                        </span>
                      )}
                    </div>
                    <div>
                      Email: <span className="text-amber-400">{entityInfo.grievance_email || 'Pending Grievance Email'}</span>
                      {!entityInfo.is_grievance_email_configured && (
                        <span className="block text-[10px] text-amber-400 mt-0.5">
                          Configure GRIEVANCE_EMAIL in backend environment
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800/80 bg-[#0c0d14] py-6 text-xs text-zinc-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <span>© 2026 {entityInfo.brand_trade_name} ({entityInfo.owner_legal_name || 'Individual Business Operator'}).</span>
          </div>
          <div className="flex items-center space-x-4">
            <button onClick={() => setActiveTab('terms')} className="hover:text-zinc-300 transition">Terms</button>
            <button onClick={() => setActiveTab('privacy')} className="hover:text-zinc-300 transition">Privacy</button>
            <button onClick={() => setActiveTab('refund')} className="hover:text-zinc-300 transition">Refunds (Draft)</button>
            <button onClick={() => setActiveTab('pricing')} className="hover:text-zinc-300 transition">Pricing</button>
            <button onClick={() => setActiveTab('contact')} className="hover:text-zinc-300 transition">Contact</button>
          </div>
        </div>
      </footer>
    </div>
  );
};
