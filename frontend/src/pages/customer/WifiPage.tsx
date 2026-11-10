import React, { useState, useEffect } from 'react';
import { Wifi, Copy, Check, Shield, Globe, ArrowLeft } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { restaurantApi } from '../../services/api';
import { Restaurant } from '../../types';

export const WifiPage: React.FC = () => {
  const { qrToken } = useParams<{ qrToken: string }>();
  const [profile, setProfile] = useState<Restaurant | null>(null);
  const [copied, setCopied] = useState(false);
  const basePath = qrToken ? `/table/${qrToken}` : '/menu';

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await restaurantApi.getProfile();
        setProfile(res);
      } catch (err) {
        console.error('Failed to load Wi-Fi details:', err);
      }
    };
    fetchProfile();
  }, []);

  const handleCopy = () => {
    if (profile?.wifi_password) {
      navigator.clipboard.writeText(profile.wifi_password);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="max-w-md mx-auto space-y-5 animate-fade-in pb-12">
      <Link
        to={basePath}
        className="inline-flex items-center space-x-1.5 text-xs font-semibold text-zinc-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Menu</span>
      </Link>

      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-2xl relative overflow-hidden">
        <div className="w-14 h-14 rounded-2xl bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center mx-auto mb-4">
          <Wifi className="w-7 h-7" />
        </div>

        <h2 className="text-xl font-bold text-white text-center">Guest Wi-Fi Network</h2>
        <p className="text-xs text-zinc-400 text-center mt-1">
          Complimentary high-speed 5GHz connectivity for our dining guests.
        </p>

        <div className="mt-6 space-y-4">
          <div className="p-4 rounded-2xl bg-zinc-900 border border-zinc-800">
            <span className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider block mb-1">
              Network Name (SSID)
            </span>
            <span className="text-sm font-bold text-white block">
              {profile?.wifi_ssid || 'RoyalSaffron-Guest-HighSpeed'}
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-between">
            <div>
              <span className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider block mb-1">
                Wi-Fi Password
              </span>
              <span className="text-sm font-mono font-bold text-brand-400 tracking-wider block">
                {profile?.wifi_password || 'SaffronDining2026'}
              </span>
            </div>

            <button
              onClick={handleCopy}
              className="px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-zinc-200 border border-zinc-700 flex items-center space-x-1.5 transition active:scale-95"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>
          </div>

          <div className="p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 space-y-2">
            <div className="flex items-center space-x-2 text-xs font-semibold text-zinc-300">
              <Globe className="w-4 h-4 text-amber-400" />
              <span>Connection Instructions</span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              {profile?.wifi_instructions ||
                '1. Open Wi-Fi settings on your phone.\n2. Connect to the RoyalSaffron network.\n3. Enter password to enjoy seamless high-speed internet during your culinary journey.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

