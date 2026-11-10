import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  SplitSquareVertical, Users, CreditCard, CheckCircle2,
  Receipt, ArrowLeft, Heart, Printer, Check
} from 'lucide-react';
import { useCart } from '../../context/CartContext';
import { billingApi, orderApi } from '../../services/api';
import { Bill, BillSplit, Order } from '../../types';

export const SplitBillPage: React.FC = () => {
  const { qrToken } = useParams<{ qrToken: string }>();
  const { tableId, tableNumber } = useCart();
  const basePath = qrToken ? `/table/${qrToken}` : '/menu';

  const [bill, setBill] = useState<Bill | null>(null);
  const [activeOrder, setActiveOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [splitMode, setSplitMode] = useState<'equal' | 'item' | 'custom'>('equal');
  const [dinerCount, setDinerCount] = useState(2);
  const [customSplits, setCustomSplits] = useState<{ person_name: string; amount: number }[]>([
    { person_name: 'Diner 1', amount: 0 },
    { person_name: 'Diner 2', amount: 0 },
  ]);
  const [tipPercentage, setTipPercentage] = useState<number>(0);
  const [payingSplitId, setPayingSplitId] = useState<number | null>(null);
  const [paymentSuccessMsg, setPaymentSuccessMsg] = useState<string | null>(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [receiptData, setReceiptData] = useState<any>(null);

  // Fetch active order and bill for current table
  const fetchActiveBill = async () => {
    if (!tableId) {
      setLoading(false);
      return;
    }
    try {
      const orders = await orderApi.getAll({ table_id: tableId });
      const currentActive = orders.find((o) => o.status !== 'COMPLETED' && o.status !== 'CANCELLED') || orders[0];
      if (currentActive) {
        setActiveOrder(currentActive);
        const b = await billingApi.getBillForOrder(currentActive.id);
        setBill(b);
      }
    } catch (err) {
      console.error('Failed to load bill:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActiveBill();
  }, [tableId]);

  const handleEqualSplitSave = async () => {
    if (!bill) return;
    const share = Math.round((bill.final_amount / dinerCount) * 100) / 100;
    const splitsPayload = Array.from({ length: dinerCount }, (_, i) => ({
      split_type: 'EQUAL',
      person_name: `Diner ${i + 1}`,
      amount: share,
    }));
    try {
      const saved = await billingApi.configureSplits(bill.id, splitsPayload);
      setBill({ ...bill, splits: saved });
    } catch (err) {
      alert('Failed to configure splits');
    }
  };

  const handleCustomSplitSave = async () => {
    if (!bill) return;
    const totalCustom = customSplits.reduce((acc, c) => acc + c.amount, 0);
    if (Math.abs(totalCustom - bill.final_amount) > 1.0) {
      alert(`Split total (₹${totalCustom}) must equal total bill amount (₹${bill.final_amount})`);
      return;
    }
    const splitsPayload = customSplits.map((c) => ({
      split_type: 'CUSTOM',
      person_name: c.person_name,
      amount: c.amount,
    }));
    try {
      const saved = await billingApi.configureSplits(bill.id, splitsPayload);
      setBill({ ...bill, splits: saved });
    } catch (err) {
      alert('Failed to configure splits');
    }
  };

  // Razorpay Sandbox Payment Simulation
  const handlePaySplitRazorpay = async (splitId?: number, amountToPay?: number) => {
    if (!bill) return;
    const payAmt = amountToPay || bill.final_amount;
    setPayingSplitId(splitId || -1);

    try {
      // 1. Create order
      const rzpOrder = await billingApi.createRazorpayOrder(bill.id, payAmt);

      // 2. Simulate Razorpay Checkout Dialog & verification
      const verifyRes = await billingApi.verifyRazorpayPayment({
        bill_id: bill.id,
        razorpay_order_id: rzpOrder.razorpay_order_id,
        razorpay_payment_id: `pay_mock_${Date.now()}`,
        razorpay_signature: 'signature_verified',
        amount: payAmt,
        split_id: splitId,
      });

      setPaymentSuccessMsg(`Payment of ₹${payAmt} successfully processed via Razorpay Sandbox!`);
      await fetchActiveBill();
      setTimeout(() => setPaymentSuccessMsg(null), 4000);
    } catch (err) {
      alert('Payment failed or cancelled.');
    } finally {
      setPayingSplitId(null);
    }
  };

  const handleViewReceipt = async () => {
    if (!bill) return;
    try {
      const rc = await billingApi.getReceipt(bill.id);
      setReceiptData(rc);
      setShowReceiptModal(true);
    } catch (err) {
      alert('Failed to load receipt.');
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center animate-fade-in">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-xs text-zinc-400">Loading bill and payment details...</p>
      </div>
    );
  }

  if (!bill) {
    return (
      <div className="p-8 text-center bg-[#12131a] rounded-2xl border border-zinc-800 max-w-md mx-auto">
        <Receipt className="w-10 h-10 text-zinc-500 mx-auto mb-2" />
        <h3 className="text-base font-bold text-white">No Active Bill Found</h3>
        <p className="text-xs text-zinc-400 mt-1">
          Place an order from the menu first to view itemized bills and split payments.
        </p>
        <Link
          to={basePath}
          className="inline-block mt-4 px-4 py-2 rounded-xl bg-brand-500 text-xs font-semibold text-white"
        >
          View Menu
        </Link>
      </div>
    );
  }

  const perPersonEqual = Math.round((bill.final_amount / dinerCount) * 100) / 100;

  return (
    <div className="max-w-xl mx-auto space-y-5 animate-fade-in pb-12">
      <Link
        to={basePath}
        className="inline-flex items-center space-x-1.5 text-xs font-semibold text-zinc-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Menu</span>
      </Link>

      {/* Payment Success Alert */}
      {paymentSuccessMsg && (
        <div className="p-4 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 flex items-center space-x-3 text-emerald-400 text-xs animate-slide-up">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <span className="font-semibold">{paymentSuccessMsg}</span>
        </div>
      )}

      {/* Bill Overview Card */}
      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-4">
          <div>
            <span className="text-[10px] font-bold text-brand-400 uppercase tracking-wider block">
              Digital Invoice
            </span>
            <h2 className="text-xl font-black text-white">{bill.bill_number}</h2>
          </div>

          <div className="text-right">
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold ${
                bill.status === 'PAID'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
              }`}
            >
              {bill.status}
            </span>
            <span className="text-[11px] text-zinc-400 block mt-1">Table {tableNumber || bill.table_id}</span>
          </div>
        </div>

        {/* Itemized Breakdown */}
        <div className="space-y-2 text-xs">
          <div className="flex justify-between text-zinc-400">
            <span>Subtotal</span>
            <span>₹{bill.subtotal.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-zinc-400">
            <span>GST ({bill.tax_percentage}%)</span>
            <span>₹{bill.tax_amount.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-zinc-400">
            <span>Service Charge ({bill.service_charge_percentage}%)</span>
            <span>₹{bill.service_charge.toFixed(2)}</span>
          </div>
          {bill.tip_amount > 0 && (
            <div className="flex justify-between text-amber-400">
              <span>Staff Tip</span>
              <span>₹{bill.tip_amount.toFixed(2)}</span>
            </div>
          )}
          <div className="pt-3 border-t border-zinc-800 flex justify-between text-lg font-black text-white">
            <span>Total Amount</span>
            <span className="text-brand-400">₹{bill.final_amount.toFixed(2)}</span>
          </div>
        </div>

        {/* Quick Full Bill Payment / Receipt */}
        <div className="mt-5 pt-4 border-t border-zinc-800 flex items-center space-x-2">
          {bill.status !== 'PAID' ? (
            <button
              onClick={() => handlePaySplitRazorpay(undefined, bill.final_amount)}
              disabled={payingSplitId !== null}
              className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-brand-600 to-amber-600 hover:from-brand-500 hover:to-amber-500 text-white font-bold text-xs shadow-lg shadow-brand-500/25 flex items-center justify-center space-x-2 transition"
            >
              <CreditCard className="w-4 h-4" />
              <span>{payingSplitId === -1 ? 'Processing...' : `Pay Full Bill (₹${bill.final_amount})`}</span>
            </button>
          ) : (
            <div className="flex-1 py-3 px-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold text-xs flex items-center justify-center space-x-2">
              <Check className="w-4 h-4" />
              <span>Bill Settled in Full</span>
            </div>
          )}

          <button
            onClick={handleViewReceipt}
            className="py-3 px-3.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white border border-zinc-700 transition"
            title="View & Print Itemized Receipt"
          >
            <Printer className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Bill Splitting Options */}
      {bill.status !== 'PAID' && (
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-6 shadow-2xl space-y-5">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-brand-500/20 text-brand-400 flex items-center justify-center">
              <SplitSquareVertical className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-white">Split Bill Calculator</h3>
              <p className="text-[11px] text-zinc-400">Choose your preferred splitting strategy</p>
            </div>
          </div>

          {/* Mode Switcher */}
          <div className="grid grid-cols-3 gap-2 p-1 bg-zinc-900 rounded-xl border border-zinc-800 text-xs font-semibold">
            <button
              onClick={() => setSplitMode('equal')}
              className={`py-2 rounded-lg transition ${
                splitMode === 'equal' ? 'bg-brand-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Split Equally
            </button>
            <button
              onClick={() => setSplitMode('custom')}
              className={`py-2 rounded-lg transition ${
                splitMode === 'custom' ? 'bg-brand-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Custom Amounts
            </button>
            <button
              onClick={() => setSplitMode('item')}
              className={`py-2 rounded-lg transition ${
                splitMode === 'item' ? 'bg-brand-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              By Item
            </button>
          </div>

          {/* Equal Split Controls */}
          {splitMode === 'equal' && (
            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-300">Number of Diners</span>
                <div className="flex items-center space-x-3 bg-zinc-900 px-3 py-1.5 rounded-xl border border-zinc-700">
                  <button
                    onClick={() => setDinerCount(Math.max(2, dinerCount - 1))}
                    className="text-zinc-400 hover:text-white font-bold px-1"
                  >
                    -
                  </button>
                  <span className="font-bold text-sm text-white">{dinerCount}</span>
                  <button
                    onClick={() => setDinerCount(dinerCount + 1)}
                    className="text-zinc-400 hover:text-white font-bold px-1"
                  >
                    +
                  </button>
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider block">
                    Each Person Pays
                  </span>
                  <span className="text-xl font-extrabold text-brand-400 block">
                    ₹{perPersonEqual.toFixed(2)}
                  </span>
                </div>

                <button
                  onClick={handleEqualSplitSave}
                  className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs font-bold text-white border border-zinc-700 transition"
                >
                  Generate {dinerCount} Split Shares
                </button>
              </div>
            </div>
          )}

          {/* Custom Split Controls */}
          {splitMode === 'custom' && (
            <div className="space-y-3 pt-2">
              {customSplits.map((cs, idx) => (
                <div key={idx} className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={cs.person_name}
                    onChange={(e) => {
                      const updated = [...customSplits];
                      updated[idx].person_name = e.target.value;
                      setCustomSplits(updated);
                    }}
                    className="flex-1 px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white"
                  />
                  <div className="relative w-32">
                    <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-xs text-zinc-500 font-bold">
                      ₹
                    </span>
                    <input
                      type="number"
                      value={cs.amount || ''}
                      onChange={(e) => {
                        const updated = [...customSplits];
                        updated[idx].amount = parseFloat(e.target.value) || 0;
                        setCustomSplits(updated);
                      }}
                      className="w-full pl-7 pr-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white"
                    />
                  </div>
                </div>
              ))}

              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={() =>
                    setCustomSplits([...customSplits, { person_name: `Diner ${customSplits.length + 1}`, amount: 0 }])
                  }
                  className="text-xs text-brand-400 hover:underline font-semibold"
                >
                  + Add Another Diner
                </button>

                <button
                  onClick={handleCustomSplitSave}
                  className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs transition"
                >
                  Confirm Custom Splits
                </button>
              </div>
            </div>
          )}

          {/* Item Split Mode */}
          {splitMode === 'item' && (
            <div className="pt-2 text-xs text-zinc-400 space-y-2">
              <p>Items in active order:</p>
              {activeOrder?.items?.map((item) => (
                <div key={item.id} className="p-2.5 rounded-xl bg-zinc-900 border border-zinc-800 flex justify-between">
                  <span>{item.quantity}x {item.item_name}</span>
                  <span className="font-bold text-white">₹{item.total_price}</span>
                </div>
              ))}
            </div>
          )}

          {/* Active Split Shares List & Pay Buttons */}
          {bill.splits && bill.splits.length > 0 && (
            <div className="pt-4 border-t border-zinc-800 space-y-2">
              <span className="text-xs font-bold text-zinc-300 block">Individual Split Shares:</span>
              <div className="space-y-2">
                {bill.splits.map((s) => (
                  <div
                    key={s.id}
                    className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-between text-xs"
                  >
                    <div>
                      <span className="font-bold text-zinc-200 block">{s.person_name}</span>
                      <span className="text-[11px] text-brand-400 font-extrabold">₹{s.amount.toFixed(2)}</span>
                    </div>

                    {s.is_paid ? (
                      <span className="px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold text-[10px]">
                        ✓ Paid
                      </span>
                    ) : (
                      <button
                        onClick={() => handlePaySplitRazorpay(s.id, s.amount)}
                        disabled={payingSplitId !== null}
                        className="px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-bold transition flex items-center space-x-1"
                      >
                        <CreditCard className="w-3.5 h-3.5" />
                        <span>{payingSplitId === s.id ? 'Processing...' : 'Pay Share'}</span>
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Printable Receipt Modal */}
      {showReceiptModal && receiptData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-white text-zinc-900 rounded-3xl max-w-sm w-full p-6 shadow-2xl relative font-mono text-xs">
            <button
              onClick={() => setShowReceiptModal(false)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-800 font-sans font-bold"
            >
              ✕
            </button>

            <div className="text-center border-b border-dashed border-zinc-300 pb-4 mb-4">
              <h2 className="font-bold text-sm tracking-tight">{receiptData.restaurant_name}</h2>
              <p className="text-[10px] text-zinc-500">GSTIN: {receiptData.restaurant_gst}</p>
              <p className="text-[10px] text-zinc-500 mt-1">Invoice: {receiptData.bill_number}</p>
              <p className="text-[10px] text-zinc-500">Date: {receiptData.date}</p>
              <p className="text-[10px] font-bold mt-1">Table: {receiptData.table_number}</p>
            </div>

            <div className="border-b border-dashed border-zinc-300 pb-3 mb-3 space-y-1">
              {receiptData.items?.map((item: any, i: number) => (
                <div key={i} className="flex justify-between">
                  <span>{item.quantity}x {item.name}</span>
                  <span className="font-bold">₹{item.total_price}</span>
                </div>
              ))}
            </div>

            <div className="space-y-1 border-b border-dashed border-zinc-300 pb-3 mb-3">
              <div className="flex justify-between">
                <span>Subtotal</span>
                <span>₹{receiptData.subtotal}</span>
              </div>
              <div className="flex justify-between">
                <span>GST ({receiptData.tax_percentage}%)</span>
                <span>₹{receiptData.tax_amount}</span>
              </div>
              <div className="flex justify-between">
                <span>Service Charge ({receiptData.service_charge_percentage}%)</span>
                <span>₹{receiptData.service_charge}</span>
              </div>
              {receiptData.tip_amount > 0 && (
                <div className="flex justify-between">
                  <span>Tip</span>
                  <span>₹{receiptData.tip_amount}</span>
                </div>
              )}
              <div className="flex justify-between font-bold text-sm pt-1 border-t border-zinc-200">
                <span>Total Amount</span>
                <span>₹{receiptData.final_amount}</span>
              </div>
            </div>

            <div className="text-center text-[10px] text-zinc-500">
              <p>Status: {receiptData.status}</p>
              <p className="mt-1">Thank you for dining with us!</p>
              <button
                onClick={() => window.print()}
                className="mt-4 w-full py-2 bg-zinc-900 text-white rounded-xl font-bold font-sans"
              >
                Print / Save PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

