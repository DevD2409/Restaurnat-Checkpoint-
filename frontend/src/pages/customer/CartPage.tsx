import React, { useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  Trash2, Plus, Minus, ArrowLeft, Utensils, CheckCircle,
  AlertCircle, Sparkles, Receipt, ArrowRight, Heart
} from 'lucide-react';
import { useCart } from '../../context/CartContext';
import { orderApi } from '../../services/api';

export const CartPage: React.FC = () => {
  const navigate = useNavigate();
  const { qrToken } = useParams<{ qrToken: string }>();
  const {
    items,
    tableId,
    tableNumber,
    restaurantId,
    customerName,
    setCustomerName,
    tipAmount,
    setTipAmount,
    orderInstructions,
    setOrderInstructions,
    updateQuantity,
    removeItem,
    clearCart,
    subtotal,
    taxAmount,
    serviceCharge,
    totalAmount
  } = useCart();

  const [customerPhone, setCustomerPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const basePath = qrToken ? `/table/${qrToken}` : '/menu';

  const handlePlaceOrder = async () => {
    if (items.length === 0) return;
    if (!tableId) {
      setError('Active table session required. Please scan a table QR code.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const orderPayload = {
        restaurant_id: restaurantId,
        table_id: tableId,
        customer_name: customerName || 'Guest',
        customer_phone: customerPhone || undefined,
        special_instructions: orderInstructions || undefined,
        tip_amount: tipAmount,
        items: items.map((i) => ({
          menu_item_id: i.menu_item_id,
          item_name: i.name,
          unit_price: i.unit_price,
          quantity: i.quantity,
          customizations: i.selected_customizations,
          special_instructions: i.special_instructions,
        })),
      };

      const createdOrder = await orderApi.create(orderPayload);
      clearCart();
      navigate(`${basePath}/track/${createdOrder.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to place order. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const tipPresets = [0, 30, 50, 100];

  if (items.length === 0) {
    return (
      <div className="py-16 text-center max-w-md mx-auto animate-fade-in pb-28">
        <div className="w-16 h-16 rounded-3xl bg-zinc-800/80 border border-zinc-700/60 mx-auto flex items-center justify-center text-zinc-500 mb-4">
          <Utensils className="w-8 h-8" />
        </div>
        <h3 className="text-lg font-bold text-zinc-200">Your Cart is Empty</h3>
        <p className="text-xs text-zinc-400 mt-1 max-w-xs mx-auto leading-relaxed">
          Explore our menu and add authentic culinary dishes to begin your dining experience.
        </p>
        <Link
          to={basePath}
          className="inline-flex items-center space-x-2 mt-6 px-5 py-2.5 rounded-2xl bg-brand-500 hover:bg-brand-600 text-white text-xs font-bold shadow-lg shadow-brand-500/20 transition active:scale-95"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Browse Digital Menu</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-5 animate-fade-in pb-32 sm:pb-16">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <Link
          to={basePath}
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-zinc-400 hover:text-white transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Menu</span>
        </Link>

        {tableNumber && (
          <span className="text-xs font-bold px-3 py-1 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700">
            Table {tableNumber}
          </span>
        )}
      </div>

      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-5 sm:p-6 shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3 mb-4">
          <div>
            <h2 className="text-lg font-extrabold text-white">Review Your Order</h2>
            <p className="text-xs text-zinc-400">Fresh dishes prepared upon confirmation</p>
          </div>
          <button
            onClick={clearCart}
            className="text-xs font-medium text-zinc-400 hover:text-red-400 flex items-center space-x-1 p-1 rounded-lg"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear</span>
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-2xl text-xs text-red-400 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Item List */}
        <div className="divide-y divide-zinc-800/80">
          {items.map((item) => {
            const addonsPrice = item.selected_customizations.reduce((acc, c) => acc + c.additional_price, 0);
            const itemTotal = (item.unit_price + addonsPrice) * item.quantity;

            return (
              <div key={item.id} className="py-3.5 flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`w-3 h-3 rounded-sm flex items-center justify-center border flex-shrink-0 ${
                        item.is_veg ? 'border-emerald-500' : 'border-red-500'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${item.is_veg ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
                    </span>
                    <h4 className="font-bold text-sm text-zinc-200 leading-tight truncate">{item.name}</h4>
                  </div>

                  {/* Customizations display */}
                  {item.selected_customizations.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {item.selected_customizations.map((c, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded-md bg-zinc-800 text-[10px] text-zinc-400 border border-zinc-700/60"
                        >
                          {c.option_name} {c.additional_price > 0 && `(+₹${c.additional_price})`}
                        </span>
                      ))}
                    </div>
                  )}

                  {item.special_instructions && (
                    <p className="text-[11px] text-amber-400/80 mt-1 italic">
                      Note: {item.special_instructions}
                    </p>
                  )}

                  <span className="text-xs font-semibold text-zinc-400 block mt-1.5">
                    ₹{item.unit_price + addonsPrice} each
                  </span>
                </div>

                {/* Quantity Controls & Price */}
                <div className="flex flex-col items-end space-y-2 flex-shrink-0">
                  <div className="flex items-center space-x-2 bg-zinc-900 px-2.5 py-1 rounded-xl border border-zinc-700/80">
                    <button
                      onClick={() => updateQuantity(item.id, -1)}
                      className="text-zinc-400 hover:text-white p-0.5"
                    >
                      <Minus className="w-3.5 h-3.5" />
                    </button>
                    <span className="text-xs font-bold text-white px-1">{item.quantity}</span>
                    <button
                      onClick={() => updateQuantity(item.id, 1)}
                      className="text-zinc-400 hover:text-white p-0.5"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <span className="text-sm font-extrabold text-white">₹{itemTotal}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Customer Details */}
        <div className="mt-6 pt-5 border-t border-zinc-800 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1 text-[10px]">
              Guest Name
            </label>
            <input
              type="text"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="e.g. Rohan Sharma"
              className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-brand-500"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1 text-[10px]">
              Phone Number (Optional)
            </label>
            <input
              type="text"
              value={customerPhone}
              onChange={(e) => setCustomerPhone(e.target.value)}
              placeholder="e.g. +91 98765 43210"
              className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-brand-500"
            />
          </div>
        </div>

        {/* Order Special Notes */}
        <div className="mt-3">
          <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1 text-[10px]">
            General Kitchen / Serving Notes
          </label>
          <input
            type="text"
            value={orderInstructions}
            onChange={(e) => setOrderInstructions(e.target.value)}
            placeholder="e.g. Serve starters first, gentle salt, extra napkins"
            className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-brand-500"
          />
        </div>

        {/* Tip Selector */}
        <div className="mt-5 pt-4 border-t border-zinc-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-zinc-300 flex items-center space-x-1.5">
              <Heart className="w-3.5 h-3.5 text-rose-500" />
              <span>Add Staff Tip</span>
            </span>
            <span className="text-xs text-brand-400 font-bold">₹{tipAmount}</span>
          </div>

          <div className="grid grid-cols-4 gap-2">
            {tipPresets.map((tip) => (
              <button
                key={tip}
                type="button"
                onClick={() => setTipAmount(tip)}
                className={`py-2 rounded-xl text-xs font-bold border transition ${
                  tipAmount === tip
                    ? 'bg-brand-500 text-white border-brand-400 shadow-md shadow-brand-500/25'
                    : 'bg-zinc-900 text-zinc-400 border-zinc-700/80 hover:bg-zinc-800'
                }`}
              >
                {tip === 0 ? 'No Tip' : `₹${tip}`}
              </button>
            ))}
          </div>
        </div>

        {/* Bill Summary */}
        <div className="mt-6 pt-5 border-t border-zinc-800 space-y-2 text-xs">
          <div className="flex justify-between text-zinc-400">
            <span>Item Subtotal</span>
            <span>₹{subtotal.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-zinc-400">
            <span>GST (5%)</span>
            <span>₹{taxAmount.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-zinc-400">
            <span>Service Charge (5%)</span>
            <span>₹{serviceCharge.toFixed(2)}</span>
          </div>
          {tipAmount > 0 && (
            <div className="flex justify-between text-amber-400">
              <span>Staff Tip</span>
              <span>₹{tipAmount.toFixed(2)}</span>
            </div>
          )}
          <div className="pt-2 border-t border-zinc-800 flex justify-between text-base font-extrabold text-white">
            <span>Total Payable</span>
            <span className="text-brand-400">₹{totalAmount.toFixed(2)}</span>
          </div>
        </div>

        {/* Place Order Button */}
        <button
          onClick={handlePlaceOrder}
          disabled={submitting}
          className="w-full mt-6 py-3.5 px-4 rounded-2xl bg-gradient-to-r from-brand-600 to-amber-600 hover:from-brand-500 hover:to-amber-500 text-white font-extrabold text-sm shadow-xl shadow-brand-500/25 transition flex items-center justify-center space-x-2 active:scale-[0.99]"
        >
          <span>{submitting ? 'Transmitting to Kitchen...' : `Place Order (₹${totalAmount.toFixed(2)})`}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
