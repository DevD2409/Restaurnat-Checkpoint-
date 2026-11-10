import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Calendar, Clock, Users, ArrowLeft, CheckCircle2, Sparkles, AlertCircle } from 'lucide-react';
import { reservationApi } from '../../services/api';

export const ReservationPage: React.FC = () => {
  const { qrToken } = useParams<{ qrToken: string }>();
  const basePath = qrToken ? `/table/${qrToken}` : '/menu';

  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [guestCount, setGuestCount] = useState(2);
  const [reservationDate, setReservationDate] = useState(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });
  const [reservationTime, setReservationTime] = useState('07:30 PM');
  const [specialRequests, setSpecialRequests] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timeSlots = [
    '12:30 PM', '01:00 PM', '01:30 PM', '02:00 PM',
    '07:00 PM', '07:30 PM', '08:00 PM', '08:30 PM', '09:00 PM', '09:30 PM'
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await reservationApi.create({
        customer_name: customerName,
        customer_phone: customerPhone,
        customer_email: customerEmail || undefined,
        guest_count: guestCount,
        reservation_date: reservationDate,
        reservation_time: reservationTime,
        special_requests: specialRequests || undefined,
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to submit reservation. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="max-w-md mx-auto p-6 bg-[#12131a] border border-zinc-800 rounded-3xl text-center space-y-4 animate-fade-in my-8 pb-32 sm:pb-16">
        <div className="w-16 h-16 rounded-3xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 mx-auto flex items-center justify-center">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-white">Reservation Confirmed!</h2>
        <p className="text-xs text-zinc-400 leading-relaxed">
          Thank you, <strong>{customerName}</strong>. Your reservation request for{' '}
          <strong className="text-white">{guestCount} guests</strong> on <strong className="text-white">{reservationDate}</strong> at{' '}
          <strong className="text-white">{reservationTime}</strong> has been received by our concierge.
        </p>
        <Link
          to={basePath}
          className="inline-block px-5 py-2.5 rounded-2xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 transition"
        >
          Return to Menu
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto space-y-5 animate-fade-in pb-32 sm:pb-16">
      <Link
        to={basePath}
        className="inline-flex items-center space-x-1.5 text-xs font-semibold text-zinc-400 hover:text-white transition"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Menu</span>
      </Link>

      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-5 sm:p-6 shadow-2xl">
        <div className="flex items-center space-x-3 mb-5">
          <div className="w-10 h-10 rounded-2xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
            <Calendar className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Book a Table</h2>
            <p className="text-xs text-zinc-400">Reserve your dining experience at The Royal Saffron</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-2xl text-xs text-red-400 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Guest Count */}
          <div>
            <label className="block text-zinc-300 font-bold mb-1.5 uppercase tracking-wider text-[10px]">
              Number of Guests
            </label>
            <div className="flex items-center space-x-3 bg-zinc-900 px-4 py-2 rounded-2xl border border-zinc-700 w-fit">
              <button
                type="button"
                onClick={() => setGuestCount(Math.max(1, guestCount - 1))}
                className="text-zinc-400 hover:text-white font-bold px-2 text-sm"
              >
                -
              </button>
              <span className="font-bold text-sm text-white px-2">{guestCount} Guests</span>
              <button
                type="button"
                onClick={() => setGuestCount(guestCount + 1)}
                className="text-zinc-400 hover:text-white font-bold px-2 text-sm"
              >
                +
              </button>
            </div>
          </div>

          {/* Date & Time */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-zinc-300 font-bold mb-1.5 uppercase tracking-wider text-[10px]">
                Date
              </label>
              <input
                type="date"
                required
                value={reservationDate}
                onChange={(e) => setReservationDate(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white focus:outline-none focus:border-brand-500"
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-bold mb-1.5 uppercase tracking-wider text-[10px]">
                Preferred Time
              </label>
              <select
                value={reservationTime}
                onChange={(e) => setReservationTime(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white focus:outline-none focus:border-brand-500"
              >
                {timeSlots.map((ts) => (
                  <option key={ts} value={ts}>
                    {ts}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Customer Contact */}
          <div>
            <label className="block text-zinc-300 font-bold mb-1.5 uppercase tracking-wider text-[10px]">
              Primary Contact Name
            </label>
            <input
              type="text"
              required
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="e.g. Vikramaditya Rathore"
              className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-brand-500"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-zinc-300 font-bold mb-1.5 uppercase tracking-wider text-[10px]">
                Phone Number
              </label>
              <input
                type="tel"
                required
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                placeholder="+91 98765 43210"
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-brand-500"
              />
            </div>

            <div>
              <label className="block text-zinc-300 font-bold mb-1.5 uppercase tracking-wider text-[10px]">
                Email (Optional)
              </label>
              <input
                type="email"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                placeholder="guest@example.com"
                className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-zinc-300 font-bold mb-1.5 uppercase tracking-wider text-[10px]">
              Special Occasion or Seating Requests
            </label>
            <textarea
              rows={2}
              value={specialRequests}
              onChange={(e) => setSpecialRequests(e.target.value)}
              placeholder="e.g. Window booth preferred, anniversary celebration"
              className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-brand-500"
            ></textarea>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3.5 px-4 rounded-2xl bg-gradient-to-r from-brand-600 to-amber-600 hover:from-brand-500 hover:to-amber-500 text-white font-extrabold text-xs shadow-xl shadow-brand-500/25 transition flex items-center justify-center space-x-2 active:scale-[0.99]"
          >
            <Sparkles className="w-4 h-4" />
            <span>{submitting ? 'Confirming Table...' : 'Confirm Table Reservation'}</span>
          </button>
        </form>
      </div>
    </div>
  );
};
