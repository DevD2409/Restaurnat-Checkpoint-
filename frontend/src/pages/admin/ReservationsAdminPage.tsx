import React, { useState, useEffect } from 'react';
import { Calendar, Users, Phone, Mail, Check, X, Clock, Table as TableIcon } from 'lucide-react';
import { reservationApi, tableApi } from '../../services/api';
import { Reservation, Table } from '../../types';

export const ReservationsAdminPage: React.FC = () => {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTableMap, setSelectedTableMap] = useState<{ [resId: number]: number }>({});

  const fetchData = async () => {
    try {
      const [resData, tableData] = await Promise.all([
        reservationApi.getAll(),
        tableApi.getAll(),
      ]);
      setReservations(resData);
      setTables(tableData);
    } catch (err) {
      console.error('Failed to load reservations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleUpdateStatus = async (resId: number, newStatus: string) => {
    const tableId = selectedTableMap[resId];
    try {
      await reservationApi.updateStatus(resId, {
        status: newStatus,
        table_id: tableId,
      });
      await fetchData();
    } catch (err) {
      alert('Failed to update reservation');
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
        <div>
          <h2 className="text-xl font-bold text-white">Table Reservations Queue</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Review guest booking requests, confirm dining slots, and allocate tables
          </p>
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-xs text-zinc-500">Loading reservations...</div>
      ) : reservations.length === 0 ? (
        <div className="py-16 text-center bg-[#12131a] border border-zinc-800 rounded-3xl">
          <Calendar className="w-10 h-10 text-zinc-600 mx-auto mb-2" />
          <h4 className="font-bold text-sm text-zinc-300">No Reservations Found</h4>
          <p className="text-xs text-zinc-500 mt-1">Upcoming bookings will appear here.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reservations.map((res) => (
            <div
              key={res.id}
              className="bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl flex flex-col justify-between space-y-4"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-sm text-white">{res.customer_name}</span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                      res.status === 'CONFIRMED'
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : res.status === 'REJECTED'
                        ? 'bg-red-500/15 text-red-400 border-red-500/30'
                        : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                    }`}
                  >
                    {res.status}
                  </span>
                </div>

                <div className="space-y-1 text-xs text-zinc-400">
                  <div className="flex items-center space-x-2">
                    <Calendar className="w-3.5 h-3.5 text-brand-400" />
                    <span>{res.reservation_date} at {res.reservation_time}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Users className="w-3.5 h-3.5 text-zinc-500" />
                    <span>{res.guest_count} Guests</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Phone className="w-3.5 h-3.5 text-zinc-500" />
                    <span>{res.customer_phone}</span>
                  </div>
                </div>

                {res.special_requests && (
                  <p className="text-[11px] text-zinc-400 italic mt-3 p-2 rounded-xl bg-zinc-900 border border-zinc-800">
                    "{res.special_requests}"
                  </p>
                )}
              </div>

              {/* Table Assignment & Action Buttons */}
              <div className="pt-3 border-t border-zinc-800 space-y-2 text-xs">
                <div className="flex items-center space-x-2">
                  <span className="text-zinc-400 text-[10px] uppercase font-bold">Assign Table:</span>
                  <select
                    value={selectedTableMap[res.id] || res.table_id || ''}
                    onChange={(e) =>
                      setSelectedTableMap({
                        ...selectedTableMap,
                        [res.id]: parseInt(e.target.value, 10),
                      })
                    }
                    className="flex-1 px-2 py-1 rounded-lg bg-zinc-900 border border-zinc-700 text-xs text-zinc-200"
                  >
                    <option value="">Select Table</option>
                    {tables.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.table_number} ({t.capacity}p - {t.section})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex space-x-2 pt-1">
                  {res.status !== 'CONFIRMED' && (
                    <button
                      onClick={() => handleUpdateStatus(res.id, 'CONFIRMED')}
                      className="flex-1 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition"
                    >
                      Confirm Booking
                    </button>
                  )}
                  {res.status !== 'REJECTED' && (
                    <button
                      onClick={() => handleUpdateStatus(res.id, 'REJECTED')}
                      className="px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-red-500/20 text-zinc-400 hover:text-red-400 text-xs transition"
                    >
                      Reject
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

