import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Utensils, Lock, User, ArrowRight, ShieldCheck, AlertCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login({ username, password });
      navigate('/admin/overview');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090a0f] flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-[#12131a] border border-zinc-800 rounded-2xl p-8 shadow-2xl relative">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 to-amber-500 mx-auto flex items-center justify-center shadow-lg shadow-brand-500/20 mb-3">
            <Utensils className="w-7 h-7 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Staff Portal Login</h2>
          <p className="text-xs text-zinc-400 mt-1">Smart Restaurant Operations Management System</p>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center space-x-2.5 text-red-400 text-xs">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-1.5">
              Username or Email
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500">
                <User className="w-4 h-4" />
              </div>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin, manager, waiter..."
                className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-1.5">
              Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-brand-600 to-amber-600 hover:from-brand-500 hover:to-amber-500 text-white font-semibold text-sm shadow-lg shadow-brand-500/25 transition flex items-center justify-center space-x-2 mt-2"
          >
            <span>{loading ? 'Signing in...' : 'Sign In to Portal'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        {/* Staff Access & Security Notice */}
        <div className="mt-8 pt-6 border-t border-zinc-800 text-center">
          <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider block mb-1.5">
            Authorized Staff & Partner Access Only
          </span>
          <p className="text-xs text-zinc-400 leading-relaxed">
            Sign in with the credentials issued for your restaurant workspace or{' '}
            <Link to="/register" className="text-amber-400 hover:text-amber-300 underline underline-offset-2">
              create a new partner workspace
            </Link>.
          </p>
        </div>

        {/* Legal & Compliance Links for Razorpay Merchant Verification */}
        <div className="mt-6 pt-4 border-t border-zinc-800/80 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[11px] text-zinc-500">
          <Link to="/terms" className="hover:text-amber-400 transition">Terms</Link>
          <span>•</span>
          <Link to="/privacy" className="hover:text-amber-400 transition">Privacy</Link>
          <span>•</span>
          <Link to="/refund" className="hover:text-amber-400 transition">Refund Policy</Link>
          <span>•</span>
          <Link to="/pricing" className="hover:text-amber-400 transition">Pricing</Link>
          <span>•</span>
          <Link to="/contact" className="hover:text-amber-400 transition">Contact Us</Link>
        </div>
      </div>
    </div>
  );
};

