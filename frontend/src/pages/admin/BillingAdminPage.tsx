import React, { useState, useEffect } from 'react';
import { Receipt, DollarSign, CreditCard, Printer, Check, Search, X } from 'lucide-react';
import { billingApi, orderApi } from '../../services/api';
import { Bill, Order } from '../../types';

export const BillingAdminPage: React.FC = () => {
  const [bills, setBills] = useState<Bill[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  // Offline Payment Modal
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedBill, setSelectedBill] = useState<Bill | null>(null);
  const [offlineAmount, setOfflineAmount] = useState(0);
  const [offlineMethod, setOfflineMethod] = useState<'CASH' | 'CARD'>('CASH');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Receipt Modal
  const [receiptData, setReceiptData] = useState<any>(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);

  const fetchData = async () => {
    try {
      const ordersData = await orderApi.getAll();
      setOrders(ordersData);

      // Collect bills for all active and completed orders
      const billPromises = ordersData.slice(0, 30).map((o) => billingApi.getBillForOrder(o.id).catch(() => null));
      const results = await Promise.all(billPromises);
      setBills(results.filter(Boolean) as Bill[]);
    } catch (err) {
      console.error('Failed to load billing history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleOpenOfflineModal = (bill: Bill) => {
    setSelectedBill(bill);
    setOfflineAmount(bill.final_amount);
    setShowPaymentModal(true);
  };

  const handleRecordOfflinePayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBill) return;
    setIsSubmitting(true);
    try {
      await billingApi.recordOfflinePayment(selectedBill.id, offlineAmount, offlineMethod);
      setShowPaymentModal(false);
      await fetchData();
    } catch (err) {
      alert('Failed to record payment');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePrintReceipt = async (billId: number) => {
    try {
      const rc = await billingApi.getReceipt(billId);
      setReceiptData(rc);
      setShowReceiptModal(true);
    } catch (err) {
      alert('Failed to load receipt.');
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
        <div>
          <h2 className="text-xl font-bold text-white">Billing & Cashier Settlements</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Monitor invoices, taxes, service charges, Razorpay transactions, and cash/card settlements
          </p>
        </div>
      </div>

      {/* Bills Table */}
      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-zinc-900/80 text-zinc-400 uppercase font-bold text-[10px] tracking-wider border-b border-zinc-800">
              <tr>
                <th className="px-6 py-4">Invoice #</th>
                <th className="px-6 py-4">Table</th>
                <th className="px-6 py-4">Subtotal</th>
                <th className="px-6 py-4">GST + Service</th>
                <th className="px-6 py-4">Tip</th>
                <th className="px-6 py-4">Total Amount</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/80">
              {bills.map((b) => (
                <tr key={b.id} className="hover:bg-zinc-800/30 transition">
                  <td className="px-6 py-4 font-mono font-bold text-white whitespace-nowrap">{b.bill_number}</td>
                  <td className="px-6 py-4 text-zinc-300 font-semibold whitespace-nowrap">Table {b.table_number || b.table_id}</td>
                  <td className="px-6 py-4 text-zinc-400 whitespace-nowrap">₹{b.subtotal.toFixed(2)}</td>
                  <td className="px-6 py-4 text-zinc-400 whitespace-nowrap">
                    ₹{(b.tax_amount + b.service_charge).toFixed(2)}
                  </td>
                  <td className="px-6 py-4 text-amber-400 whitespace-nowrap">₹{b.tip_amount.toFixed(2)}</td>
                  <td className="px-6 py-4 font-black text-brand-400 text-sm whitespace-nowrap">
                    ₹{b.final_amount.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                        b.status === 'PAID'
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                      }`}
                    >
                      {b.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-1.5">
                    {b.status !== 'PAID' && (
                      <button
                        onClick={() => handleOpenOfflineModal(b)}
                        className="px-2.5 py-1 rounded-lg bg-brand-500 hover:bg-brand-600 text-white font-bold text-[11px] transition"
                      >
                        Settle Cash/Card
                      </button>
                    )}
                    <button
                      onClick={() => handlePrintReceipt(b.id)}
                      className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition"
                      title="Print receipt"
                    >
                      <Printer className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Offline Payment Modal */}
      {showPaymentModal && selectedBill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-[#181924] border border-zinc-700 rounded-3xl max-w-sm w-full p-6 shadow-2xl relative text-xs">
            <button
              onClick={() => setShowPaymentModal(false)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-bold text-white mb-2">Record Settlement</h3>
            <p className="text-zinc-400 mb-4">Invoice {selectedBill.bill_number}</p>

            <form onSubmit={handleRecordOfflinePayment} className="space-y-4">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Amount Collected (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={offlineAmount}
                  onChange={(e) => setOfflineAmount(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white font-bold"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Settlement Method
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setOfflineMethod('CASH')}
                    className={`py-2 rounded-xl font-bold border transition ${
                      offlineMethod === 'CASH'
                        ? 'bg-brand-500 text-white border-brand-400'
                        : 'bg-zinc-900 text-zinc-400 border-zinc-800'
                    }`}
                  >
                    💵 Cash
                  </button>
                  <button
                    type="button"
                    onClick={() => setOfflineMethod('CARD')}
                    className={`py-2 rounded-xl font-bold border transition ${
                      offlineMethod === 'CARD'
                        ? 'bg-brand-500 text-white border-brand-400'
                        : 'bg-zinc-900 text-zinc-400 border-zinc-800'
                    }`}
                  >
                    💳 Terminal Card
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-lg shadow-emerald-600/25 transition mt-2"
              >
                {isSubmitting ? 'Recording...' : `Confirm Payment (₹${offlineAmount})`}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Receipt Modal */}
      {showReceiptModal && receiptData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-white text-zinc-900 rounded-3xl max-w-sm w-full p-6 shadow-2xl relative font-mono text-xs">
            <button
              onClick={() => setShowReceiptModal(false)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-800 font-sans font-bold"
            >
              ✕
            </button>

            <div className="text-center border-b border-dashed border-zinc-300 pb-3 mb-3">
              <h2 className="font-bold text-sm">{receiptData.restaurant_name}</h2>
              <p className="text-[10px] text-zinc-500">GSTIN: {receiptData.restaurant_gst}</p>
              <p className="text-[10px] text-zinc-500">Bill: {receiptData.bill_number}</p>
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

            <button
              onClick={() => window.print()}
              className="w-full py-2 bg-zinc-900 text-white rounded-xl font-bold font-sans"
            >
              Print Receipt
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

