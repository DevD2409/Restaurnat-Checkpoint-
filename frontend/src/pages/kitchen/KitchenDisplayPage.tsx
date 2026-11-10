import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Clock, AlertTriangle, CheckCircle, ChefHat, Flame,
  Check, Utensils, Volume2, ArrowRight
} from 'lucide-react';
import { kitchenApi } from '../../services/api';
import { useWebSocket } from '../../context/WebSocketContext';

interface KitchenOrder {
  id: number;
  order_number: string;
  table_id: number;
  table_number: string;
  customer_name: string;
  status: string;
  priority: string;
  special_instructions?: string;
  created_at: string;
  elapsed_minutes: number;
  estimated_prep_time: number;
  is_delayed: boolean;
  items: {
    id: number;
    name: string;
    quantity: number;
    customizations_json?: string;
    special_instructions?: string;
    status: string;
  }[];
}

export const KitchenDisplayPage: React.FC = () => {
  const { soundEnabled } = useOutletContext<{ soundEnabled: boolean }>();
  const { lastEvent, connectChannel } = useWebSocket();

  const [activeData, setActiveData] = useState<{
    new_orders: KitchenOrder[];
    preparing: KitchenOrder[];
    ready: KitchenOrder[];
    completed: KitchenOrder[];
    total_active: number;
  }>({
    new_orders: [],
    preparing: [],
    ready: [],
    completed: [],
    total_active: 0,
  });

  const [loading, setLoading] = useState(true);
  const [selectedTab, setSelectedTab] = useState<'all' | 'new' | 'prep' | 'ready' | 'done'>('all');
  const audioContextRef = useRef<AudioContext | null>(null);

  // Play synthetic chime via Web Audio API without needing external mp3 files
  const playAlertChime = () => {
    if (!soundEnabled) return;
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const ctx = audioContextRef.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(880.0, ctx.currentTime + 0.15);

      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } catch (e) {
      console.warn('Audio chime warning:', e);
    }
  };

  const fetchActiveOrders = async () => {
    try {
      const data = await kitchenApi.getActiveOrders();
      setActiveData(data);
    } catch (err) {
      console.error('Failed to load kitchen orders:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    connectChannel('kitchen');
    fetchActiveOrders();

    const interval = setInterval(fetchActiveOrders, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!lastEvent) return;
    if (
      lastEvent.type === 'ORDER_PLACED' ||
      lastEvent.type === 'ORDER_STATUS_CHANGED' ||
      lastEvent.type === 'ORDER_PRIORITY_CHANGED'
    ) {
      if (lastEvent.type === 'ORDER_PLACED') {
        playAlertChime();
      }
      fetchActiveOrders();
    }
  }, [lastEvent]);

  const handleUpdateStatus = async (orderId: number, newStatus: string) => {
    try {
      await kitchenApi.updateStatus(orderId, newStatus, 'Kitchen Chef');
      await fetchActiveOrders();
    } catch (err) {
      alert('Failed to update status.');
    }
  };

  const renderOrderCard = (order: KitchenOrder, currentColumn: 'new' | 'prep' | 'ready' | 'done') => {
    const isActuallyDelayed = order.is_delayed && currentColumn !== 'done';

    return (
      <div
        key={order.id}
        className={`bg-[#14151f] rounded-2xl border transition shadow-xl p-4 flex flex-col justify-between ${
          isActuallyDelayed
            ? 'border-red-500/80 shadow-red-500/10 ring-1 ring-red-500/50'
            : order.priority === 'URGENT'
            ? 'border-amber-500/80 shadow-amber-500/10'
            : 'border-zinc-800 hover:border-zinc-700'
        }`}
      >
        <div>
          {/* Card Header: Table + Time Elapsed */}
          <div className="flex items-center justify-between mb-3 border-b border-zinc-800/80 pb-2.5">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-black text-white px-2.5 py-1 rounded-xl bg-zinc-800 border border-zinc-700 whitespace-nowrap">
                Table {order.table_number}
              </span>
              <span className="text-xs text-zinc-400 font-mono">#{order.order_number.slice(-3)}</span>
            </div>

            <div className="flex items-center space-x-2">
              {isActuallyDelayed && (
                <span className="px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 font-bold text-[10px] flex items-center space-x-1 animate-pulse">
                  <AlertTriangle className="w-3 h-3" />
                  <span>DELAYED</span>
                </span>
              )}

              {order.priority === 'URGENT' && (
                <span className="px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 font-bold text-[10px]">
                  VIP
                </span>
              )}

              <span
                className={`text-xs font-mono font-bold flex items-center space-x-1 ${
                  isActuallyDelayed ? 'text-red-400' : 'text-zinc-400'
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                <span>{order.elapsed_minutes}m</span>
              </span>
            </div>
          </div>

          {/* Dish Items List */}
          <div className="space-y-2 mb-3">
            {order.items.map((item) => {
              let parsedAddons: any[] = [];
              try {
                if (item.customizations_json) {
                  parsedAddons = JSON.parse(item.customizations_json);
                }
              } catch (e) {}

              return (
                <div key={item.id} className="text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="w-5 h-5 rounded-md bg-brand-500/20 text-brand-400 font-bold flex items-center justify-center text-[11px] flex-shrink-0">
                        {item.quantity}
                      </span>
                      <span className="font-semibold text-zinc-100">{item.name}</span>
                    </div>
                  </div>

                  {/* Addon Pills */}
                  {parsedAddons.length > 0 && (
                    <div className="ml-7 mt-1 flex flex-wrap gap-1">
                      {parsedAddons.map((ad, idx) => (
                        <span
                          key={idx}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700/50"
                        >
                          {ad.option_name}
                        </span>
                      ))}
                    </div>
                  )}

                  {item.special_instructions && (
                    <div className="ml-7 mt-0.5 text-[10px] text-amber-400 italic">
                      Note: {item.special_instructions}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {order.special_instructions && (
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 mb-3 leading-snug">
              <strong>Order Note:</strong> {order.special_instructions}
            </div>
          )}
        </div>

        {/* Action Button Progression */}
        <div className="pt-3 border-t border-zinc-800/80">
          {currentColumn === 'new' && (
            <button
              onClick={() => handleUpdateStatus(order.id, 'PREPARING')}
              className="w-full py-2.5 px-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-black font-extrabold text-xs shadow-md shadow-amber-500/20 flex items-center justify-center space-x-1.5 transition active:scale-95"
            >
              <Flame className="w-3.5 h-3.5" />
              <span>Accept & Start Cooking</span>
            </button>
          )}

          {currentColumn === 'prep' && (
            <button
              onClick={() => handleUpdateStatus(order.id, 'READY')}
              className="w-full py-2.5 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-extrabold text-xs shadow-md shadow-emerald-500/20 flex items-center justify-center space-x-1.5 transition active:scale-95"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Mark Dish Ready</span>
            </button>
          )}

          {currentColumn === 'ready' && (
            <button
              onClick={() => handleUpdateStatus(order.id, 'SERVED')}
              className="w-full py-2.5 px-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-extrabold text-xs shadow-md shadow-brand-500/20 flex items-center justify-center space-x-1.5 transition active:scale-95"
            >
              <Utensils className="w-3.5 h-3.5" />
              <span>Mark Served to Table</span>
            </button>
          )}

          {currentColumn === 'done' && (
            <div className="text-center text-[11px] text-zinc-500 font-semibold py-1">
              ✓ Completed & Served
            </div>
          )}
        </div>
      </div>
    );
  };

  const showCol = (colKey: string) => {
    return selectedTab === 'all' || selectedTab === colKey;
  };

  return (
    <div className="h-full space-y-4 animate-fade-in pb-12">
      {/* Responsive Column Selector for Mobile & Tablets */}
      <div className="flex xl:hidden items-center space-x-1.5 overflow-x-auto pb-1 scrollbar-none">
        <button
          onClick={() => setSelectedTab('all')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition ${
            selectedTab === 'all'
              ? 'bg-brand-500 text-white'
              : 'bg-zinc-900 text-zinc-400 border border-zinc-800'
          }`}
        >
          All Columns
        </button>
        <button
          onClick={() => setSelectedTab('new')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap flex items-center space-x-1.5 transition ${
            selectedTab === 'new'
              ? 'bg-amber-500 text-black'
              : 'bg-zinc-900 text-zinc-400 border border-zinc-800'
          }`}
        >
          <span>New</span>
          <span className="px-1.5 py-0.2 rounded-full bg-black/20 text-[10px]">
            {activeData.new_orders.length}
          </span>
        </button>
        <button
          onClick={() => setSelectedTab('prep')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap flex items-center space-x-1.5 transition ${
            selectedTab === 'prep'
              ? 'bg-orange-500 text-white'
              : 'bg-zinc-900 text-zinc-400 border border-zinc-800'
          }`}
        >
          <span>Cooking</span>
          <span className="px-1.5 py-0.2 rounded-full bg-black/20 text-[10px]">
            {activeData.preparing.length}
          </span>
        </button>
        <button
          onClick={() => setSelectedTab('ready')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap flex items-center space-x-1.5 transition ${
            selectedTab === 'ready'
              ? 'bg-emerald-500 text-white'
              : 'bg-zinc-900 text-zinc-400 border border-zinc-800'
          }`}
        >
          <span>Ready</span>
          <span className="px-1.5 py-0.2 rounded-full bg-black/20 text-[10px]">
            {activeData.ready.length}
          </span>
        </button>
        <button
          onClick={() => setSelectedTab('done')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap flex items-center space-x-1.5 transition ${
            selectedTab === 'done'
              ? 'bg-blue-600 text-white'
              : 'bg-zinc-900 text-zinc-400 border border-zinc-800'
          }`}
        >
          <span>Completed</span>
          <span className="px-1.5 py-0.2 rounded-full bg-black/20 text-[10px]">
            {activeData.completed.length}
          </span>
        </button>
      </div>

      {/* Kanban Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 h-full items-start">
        {/* Column 1: New Orders */}
        {showCol('new') && (
          <div className="bg-[#0f1017] rounded-3xl border border-zinc-800 p-4 flex flex-col max-h-[82vh]">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-zinc-800">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping"></span>
                <h3 className="font-extrabold text-sm text-zinc-200 uppercase tracking-wide">
                  New Orders
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-bold text-xs">
                {activeData.new_orders.length}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {activeData.new_orders.length === 0 ? (
                <p className="text-xs text-zinc-600 text-center py-10">No pending new orders</p>
              ) : (
                activeData.new_orders.map((o) => renderOrderCard(o, 'new'))
              )}
            </div>
          </div>
        )}

        {/* Column 2: In Preparation */}
        {showCol('prep') && (
          <div className="bg-[#0f1017] rounded-3xl border border-zinc-800 p-4 flex flex-col max-h-[82vh]">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-zinc-800">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-orange-500"></span>
                <h3 className="font-extrabold text-sm text-zinc-200 uppercase tracking-wide">
                  Cooking / Prep
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 font-bold text-xs">
                {activeData.preparing.length}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {activeData.preparing.length === 0 ? (
                <p className="text-xs text-zinc-600 text-center py-10">No dishes currently cooking</p>
              ) : (
                activeData.preparing.map((o) => renderOrderCard(o, 'prep'))
              )}
            </div>
          </div>
        )}

        {/* Column 3: Ready to Serve */}
        {showCol('ready') && (
          <div className="bg-[#0f1017] rounded-3xl border border-zinc-800 p-4 flex flex-col max-h-[82vh]">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-zinc-800">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                <h3 className="font-extrabold text-sm text-zinc-200 uppercase tracking-wide">
                  Ready to Serve
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-xs">
                {activeData.ready.length}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {activeData.ready.length === 0 ? (
                <p className="text-xs text-zinc-600 text-center py-10">No plated orders waiting</p>
              ) : (
                activeData.ready.map((o) => renderOrderCard(o, 'ready'))
              )}
            </div>
          </div>
        )}

        {/* Column 4: Recently Completed */}
        {showCol('done') && (
          <div className="bg-[#0f1017] rounded-3xl border border-zinc-800 p-4 flex flex-col max-h-[82vh]">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-zinc-800">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                <h3 className="font-extrabold text-sm text-zinc-200 uppercase tracking-wide">
                  Completed
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 font-bold text-xs">
                {activeData.completed.length}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {activeData.completed.length === 0 ? (
                <p className="text-xs text-zinc-600 text-center py-10">No completed orders yet</p>
              ) : (
                activeData.completed.map((o) => renderOrderCard(o, 'done'))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
