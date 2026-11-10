import React, { useState, useEffect } from 'react';
import { Outlet, Link } from 'react-router-dom';
import { ChefHat, Volume2, VolumeX, ArrowLeft, Clock } from 'lucide-react';

export const KitchenLayout: React.FC = () => {
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-[#07080b] text-zinc-100 flex flex-col font-sans select-none">
      {/* KDS Header */}
      <header className="bg-[#0f1017] border-b border-zinc-800/80 px-3 sm:px-6 py-2.5 sm:py-3 flex flex-wrap items-center justify-between gap-2 shadow-lg">
        <div className="flex items-center space-x-2.5 sm:space-x-4">
          <Link
            to="/admin/overview"
            className="flex items-center space-x-1 px-2.5 py-1.5 rounded-xl bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 text-xs font-semibold border border-zinc-700/60 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Admin</span>
          </Link>

          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <ChefHat className="w-4 h-4 sm:w-5 sm:h-5" />
            </div>
            <div>
              <h1 className="text-sm sm:text-base font-bold text-white tracking-wide leading-none">
                Kitchen Display System (KDS)
              </h1>
              <span className="text-[10px] text-zinc-400 font-medium hidden sm:block">
                Live Culinary Operations & Order Dispatch
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 sm:space-x-3">
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-mono text-amber-400 font-semibold">
            <Clock className="w-3 h-3" />
            <span>{currentTime}</span>
          </div>

          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-xl border text-xs font-semibold transition ${
              soundEnabled
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : 'bg-zinc-800 text-zinc-400 border-zinc-700'
            }`}
          >
            {soundEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">{soundEnabled ? 'Chime ON' : 'Muted'}</span>
          </button>
        </div>
      </header>

      {/* KDS Main Kanban Board */}
      <main className="flex-1 p-3 sm:p-6 overflow-y-auto">
        <Outlet context={{ soundEnabled }} />
      </main>
    </div>
  );
};
