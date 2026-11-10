import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Clock, ChefHat, CheckCircle2, AlertCircle, Bell,
  FileText, Flame, UtensilsCrossed, Sparkles, ArrowLeft,
  CheckCircle, PartyPopper
} from 'lucide-react';
import { orderApi } from '../../services/api';
import { useWebSocket } from '../../context/WebSocketContext';
import { Order, OrderStatus } from '../../types';

export const OrderTrackingPage: React.FC = () => {
  const { orderId, qrToken } = useParams<{ orderId: string; qrToken: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { lastEvent, connectChannel } = useWebSocket();
  const basePath = qrToken ? `/table/${qrToken}` : '/menu';

  const orderStages: { status: OrderStatus; label: string; desc: string; icon: React.FC<{ className?: string }> }[] = [
    { status: 'PLACED', label: 'Order Placed', desc: 'Received by kitchen system', icon: FileText },
    { status: 'ACCEPTED', label: 'Order Accepted', desc: 'Queued at executive chef station', icon: CheckCircle },
    { status: 'PREPARING', label: 'Preparing', desc: 'Cooking with fresh ingredients', icon: Flame },
    { status: 'READY', label: 'Ready to Serve', desc: 'Plated & awaiting table runner', icon: UtensilsCrossed },
    { status: 'SERVED', label: 'Served', desc: 'Delivered to your table', icon: Sparkles },
    { status: 'COMPLETED', label: 'Completed', desc: 'Dining experience concluded', icon: CheckCircle2 },
  ];

  const fetchOrder = async () => {
    if (!orderId) return;
    try {
      const data = await orderApi.getById(parseInt(orderId, 10));
      setOrder(data);
      if (data.table_id) {
        connectChannel(`table/${data.table_id}`);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Order not found');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrder();
  }, [orderId]);

  // Handle incoming real-time WebSocket events
  useEffect(() => {
    if (!lastEvent) return;
    if (
      lastEvent.type === 'ORDER_STATUS_CHANGED' &&
      lastEvent.data.order_id === parseInt(orderId || '0', 10)
    ) {
      fetchOrder();
    }
  }, [lastEvent, orderId]);

  if (loading) {
    return (
      <div className="py-20 text-center animate-fade-in pb-28">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-xs text-zinc-400">Loading order tracker...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="p-8 text-center bg-[#12131a] rounded-3xl border border-zinc-800 max-w-md mx-auto my-12 pb-28">
        <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-2" />
        <h3 className="text-base font-bold text-white">Order Tracking Error</h3>
        <p className="text-xs text-zinc-400 mt-1">{error || 'Could not find this order.'}</p>
        <Link
          to={basePath}
          className="inline-block mt-4 px-4 py-2 rounded-xl bg-zinc-800 text-xs font-semibold text-zinc-200"
        >
          Return to Menu
        </Link>
      </div>
    );
  }

  const currentStageIndex = orderStages.findIndex((s) => s.status === order.status);

  return (
    <div className="max-w-xl mx-auto space-y-5 animate-fade-in pb-32 sm:pb-16">
      <Link
        to={basePath}
        className="inline-flex items-center space-x-1.5 text-xs font-semibold text-zinc-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Menu</span>
      </Link>

      {/* Main Status Header Card */}
      <div className="bg-gradient-to-br from-[#181924] to-[#12131a] border border-zinc-800 rounded-3xl p-5 sm:p-6 shadow-2xl relative overflow-hidden">
        <div className="flex items-center justify-between mb-4">
          <div>
            <span className="text-[10px] font-bold text-brand-400 tracking-wider uppercase block">
              Live Order Tracker
            </span>
            <h2 className="text-xl font-black text-white mt-0.5">
              {order.order_number}
            </h2>
          </div>

          <div className="text-right">
            <span className="text-xs font-bold px-3 py-1 rounded-full bg-brand-500/15 text-brand-400 border border-brand-500/30">
              Table {order.table_number || order.table_id}
            </span>
            <span className="text-[10px] text-zinc-400 block mt-1">
              {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        </div>

        {/* Dynamic Status Progress Bar */}
        <div className="mt-8 mb-8 px-2">
          <div className="relative flex items-center justify-between">
            <div className="absolute top-1/2 left-0 right-0 -translate-y-1/2 h-1 bg-zinc-800 -z-0"></div>
            <div
              className="absolute top-1/2 left-0 -translate-y-1/2 h-1 bg-gradient-to-r from-brand-600 to-amber-500 transition-all duration-500 -z-0"
              style={{
                width: `${Math.max(0, (currentStageIndex / (orderStages.length - 1)) * 100)}%`,
              }}
            ></div>

            {orderStages.map((stage, idx) => {
              const isPastOrCurrent = idx <= currentStageIndex;
              const isCurrent = idx === currentStageIndex;
              const StageIcon = stage.icon;

              return (
                <div key={stage.status} className="relative z-10 flex flex-col items-center">
                  <div
                    className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                      isCurrent
                        ? 'bg-brand-500 text-white ring-4 ring-brand-500/25 scale-110 shadow-lg shadow-brand-500/30'
                        : isPastOrCurrent
                        ? 'bg-amber-600 text-white'
                        : 'bg-zinc-800 text-zinc-500 border border-zinc-700'
                    }`}
                  >
                    <StageIcon className="w-4 h-4" />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Current Stage Label Highlight */}
          <div className="mt-5 p-3.5 rounded-2xl bg-zinc-900/90 border border-zinc-800 text-center">
            <span className="text-xs font-black text-brand-400 uppercase tracking-wide block">
              Current Stage: {orderStages[currentStageIndex]?.label || order.status}
            </span>
            <span className="text-xs text-zinc-300 mt-0.5 block">
              {orderStages[currentStageIndex]?.desc}
            </span>
          </div>
        </div>

        {/* Order Items Breakdown */}
        <div className="border-t border-zinc-800 pt-4">
          <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider mb-3">
            Ordered Dishes ({order.items.length})
          </h4>
          <div className="space-y-2">
            {order.items.map((item) => (
              <div key={item.id} className="flex justify-between items-center text-xs">
                <div className="flex items-center space-x-2">
                  <span className="w-5 h-5 rounded-md bg-zinc-800 text-brand-400 font-extrabold flex items-center justify-center text-[10px]">
                    {item.quantity}×
                  </span>
                  <span className="font-medium text-zinc-200">{item.item_name}</span>
                </div>
                <span className="font-bold text-zinc-300">₹{item.total_price.toFixed(2)}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-3 border-t border-zinc-800/80 flex justify-between items-center text-xs">
            <span className="text-zinc-400">Total Billed</span>
            <span className="text-base font-extrabold text-white">₹{order.total_amount.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
