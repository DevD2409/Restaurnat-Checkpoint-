import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Bell, CheckCircle2, Clock, Utensils, Grid, AlertCircle,
  Check, ArrowRight, UserCheck, ShieldCheck
} from 'lucide-react';
import { serviceRequestApi, tableApi } from '../../services/api';
import { useWebSocket } from '../../context/WebSocketContext';
import { useAuth } from '../../context/AuthContext';
import { ServiceRequest, Table, ServiceRequestStatus } from '../../types';

export const StaffDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const { lastEvent, connectChannel } = useWebSocket();

  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'PENDING' | 'RESOLVED'>('ALL');

  const fetchData = async () => {
    try {
      const [reqData, tableData] = await Promise.all([
        serviceRequestApi.getAll(),
        tableApi.getAll(),
      ]);
      setRequests(reqData);
      setTables(tableData);
    } catch (err) {
      console.error('Failed to load staff portal data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    connectChannel('staff');
    fetchData();
  }, []);

  // Handle incoming WebSocket events
  useEffect(() => {
    if (!lastEvent) return;
    if (
      lastEvent.type === 'SERVICE_REQUEST_CREATED' ||
      lastEvent.type === 'SERVICE_REQUEST_UPDATED' ||
      lastEvent.type === 'TABLE_STATUS_CHANGED' ||
      lastEvent.type === 'ORDER_PLACED'
    ) {
      fetchData();
    }
  }, [lastEvent]);

  const handleUpdateStatus = async (reqId: number, newStatus: ServiceRequestStatus) => {
    try {
      await serviceRequestApi.updateStatus(reqId, newStatus, undefined, user?.id);
      await fetchData();
    } catch (err) {
      alert('Failed to update service request.');
    }
  };

  const pendingCount = requests.filter((r) => r.status === 'PENDING').length;
  const occupiedTables = tables.filter((t) => t.status !== 'Available').length;

  const filteredRequests = requests.filter((r) => {
    if (filterStatus === 'PENDING') return r.status === 'PENDING' || r.status === 'ACKNOWLEDGED';
    if (filterStatus === 'RESOLVED') return r.status === 'RESOLVED';
    return true;
  });

  return (
    <div className="min-h-screen bg-[#090a0f] text-zinc-100 p-4 sm:p-6 space-y-5 sm:space-y-6 font-sans pb-16">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
        <div className="flex items-center space-x-3.5">
          <div className="w-11 h-11 rounded-2xl bg-brand-500/20 text-brand-400 border border-brand-500/30 flex items-center justify-center">
            <Bell className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white leading-tight">
              Staff & Waiter Operations Hub
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">
              Logged in as <strong className="text-white">{user?.full_name || 'Staff Member'}</strong> ({user?.role || 'WAITER'})
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2.5">
          <Link
            to="/admin/tables"
            className="px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-zinc-200 border border-zinc-700 flex items-center space-x-2 transition"
          >
            <Grid className="w-4 h-4 text-brand-400" />
            <span>Floor Map</span>
          </Link>
          <Link
            to="/kitchen"
            className="px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-black text-xs font-extrabold flex items-center space-x-2 transition shadow-lg shadow-amber-500/20"
          >
            <Utensils className="w-4 h-4" />
            <span>Kitchen KDS</span>
          </Link>
        </div>
      </div>

      {/* Quick KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-4">
          <span className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider block">
            Pending Waiter Calls
          </span>
          <span className="text-2xl font-black text-amber-400 mt-1 block">
            {pendingCount}
          </span>
        </div>

        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-4">
          <span className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider block">
            Occupied Dining Tables
          </span>
          <span className="text-2xl font-black text-white mt-1 block">
            {occupiedTables} / {tables.length}
          </span>
        </div>

        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-4">
          <span className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider block">
            Tables Requesting Bill
          </span>
          <span className="text-2xl font-black text-brand-400 mt-1 block">
            {tables.filter((t) => t.status === 'Bill Requested').length}
          </span>
        </div>

        <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-4">
          <span className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider block">
            Tables Awaiting Cleaning
          </span>
          <span className="text-2xl font-black text-blue-400 mt-1 block">
            {tables.filter((t) => t.status === 'Cleaning').length}
          </span>
        </div>
      </div>

      {/* Service Requests Queue */}
      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl p-5 sm:p-6 shadow-2xl">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-base font-bold text-white">Live Guest Service Requests</h2>
            <p className="text-xs text-zinc-400">Direct assistance and waiter call queue from dining tables</p>
          </div>

          <div className="flex items-center bg-zinc-900 p-1 rounded-2xl border border-zinc-800 text-xs font-semibold">
            <button
              onClick={() => setFilterStatus('ALL')}
              className={`px-3 py-1.5 rounded-xl transition ${
                filterStatus === 'ALL' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilterStatus('PENDING')}
              className={`px-3 py-1.5 rounded-xl transition ${
                filterStatus === 'PENDING' ? 'bg-amber-600 text-white' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Active ({pendingCount})
            </button>
            <button
              onClick={() => setFilterStatus('RESOLVED')}
              className={`px-3 py-1.5 rounded-xl transition ${
                filterStatus === 'RESOLVED' ? 'bg-emerald-600 text-white' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Resolved
            </button>
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-zinc-500">Loading service requests...</div>
        ) : filteredRequests.length === 0 ? (
          <div className="py-12 text-center text-xs text-zinc-500">
            No active service requests right now. All guests are attended to!
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredRequests.map((req) => (
              <div
                key={req.id}
                className={`p-4 rounded-3xl border transition shadow-lg flex flex-col justify-between ${
                  req.status === 'PENDING'
                    ? 'bg-[#181924] border-amber-500/50 ring-1 ring-amber-500/30'
                    : req.status === 'ACKNOWLEDGED'
                    ? 'bg-[#14151f] border-brand-500/40'
                    : 'bg-[#101118] border-zinc-800 opacity-75'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-extrabold text-white px-2.5 py-0.5 rounded-xl bg-zinc-800 border border-zinc-700">
                      Table {req.table_number || req.table_id}
                    </span>

                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        req.status === 'PENDING'
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30 animate-pulse'
                          : req.status === 'ACKNOWLEDGED'
                          ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30'
                          : 'bg-emerald-500/20 text-emerald-400'
                      }`}
                    >
                      {req.status}
                    </span>
                  </div>

                  <h4 className="text-base font-bold text-zinc-100 mt-2">
                    {req.request_type === 'CALL_WAITER' && '👋 Call Waiter'}
                    {req.request_type === 'WATER' && '💧 Water Requested'}
                    {req.request_type === 'CUTLERY' && '🍴 Cutlery / Napkins'}
                    {req.request_type === 'BILL' && '🧾 Bill Requested'}
                    {req.request_type === 'ASSISTANCE' && '❓ Assistance Needed'}
                  </h4>

                  {req.customer_notes && (
                    <p className="text-xs text-zinc-300 mt-1 italic">
                      "{req.customer_notes}"
                    </p>
                  )}

                  <span className="text-[10px] text-zinc-500 block mt-3">
                    Requested at: {new Date(req.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <div className="mt-4 pt-3 border-t border-zinc-800 flex items-center space-x-2">
                  {req.status === 'PENDING' && (
                    <button
                      onClick={() => handleUpdateStatus(req.id, 'ACKNOWLEDGED')}
                      className="flex-1 py-2 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs transition active:scale-95 shadow-md shadow-brand-500/20"
                    >
                      Acknowledge Call
                    </button>
                  )}

                  {req.status === 'ACKNOWLEDGED' && (
                    <button
                      onClick={() => handleUpdateStatus(req.id, 'RESOLVED')}
                      className="flex-1 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition active:scale-95 shadow-md shadow-emerald-500/20"
                    >
                      Mark Resolved
                    </button>
                  )}

                  {req.status === 'RESOLVED' && (
                    <span className="text-[11px] text-zinc-500 font-semibold py-1">
                      ✓ Resolved by staff
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
