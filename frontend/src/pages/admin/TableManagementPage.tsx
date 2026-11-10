import React, { useState, useEffect } from 'react';
import {
  Grid, Plus, QrCode, RefreshCw, Users, Clock,
  CheckCircle, AlertCircle, Edit, Trash2, Printer, X
} from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { tableApi } from '../../services/api';
import { useWebSocket } from '../../context/WebSocketContext';
import { Table, TableStatus } from '../../types';

export const TableManagementPage: React.FC = () => {
  const { lastEvent, connectChannel } = useWebSocket();
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSection, setSelectedSection] = useState<string>('All');
  const [statusFilter, setStatusFilter] = useState<string>('All');

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [qrModalTable, setQrModalTable] = useState<Table | null>(null);

  // New Table Form
  const [newTableNum, setNewTableNum] = useState('');
  const [newCapacity, setNewCapacity] = useState(4);
  const [newSection, setNewSection] = useState('Main Dining');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchTables = async () => {
    try {
      const data = await tableApi.getAll();
      setTables(data);
    } catch (err) {
      console.error('Failed to load tables:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    connectChannel('admin');
    fetchTables();
  }, []);

  // Real-time WebSocket updates
  useEffect(() => {
    if (!lastEvent) return;
    if (
      lastEvent.type === 'TABLE_STATUS_CHANGED' ||
      lastEvent.type === 'TABLE_OCCUPIED' ||
      lastEvent.type === 'TABLE_FREED' ||
      lastEvent.type === 'ORDER_PLACED'
    ) {
      fetchTables();
    }
  }, [lastEvent]);

  const handleStatusChange = async (tableId: number, newStatus: TableStatus) => {
    try {
      await tableApi.update(tableId, { status: newStatus });
      await fetchTables();
    } catch (err) {
      alert('Failed to update table status');
    }
  };

  const handleCreateTable = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTableNum) return;
    setIsSubmitting(true);
    try {
      await tableApi.create({
        table_number: newTableNum,
        capacity: newCapacity,
        section: newSection,
        status: 'Available',
      });
      setShowAddModal(false);
      setNewTableNum('');
      await fetchTables();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to create table');
    } finally {
      setIsSubmitting(false);
    }
  };

  const sections = ['All', 'Main Dining', 'Terrace Garden', 'Window Booth', 'VIP Lounge'];
  const statusOptions: TableStatus[] = [
    'Available',
    'Occupied',
    'Reserved',
    'Cleaning',
    'Order Pending',
    'Bill Requested',
  ];

  const filteredTables = tables.filter((t) => {
    if (selectedSection !== 'All' && t.section !== selectedSection) return false;
    if (statusFilter !== 'All' && t.status !== statusFilter) return false;
    return true;
  });

  const getStatusColor = (status: TableStatus) => {
    switch (status) {
      case 'Available':
        return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400';
      case 'Occupied':
        return 'border-blue-500/40 bg-blue-500/10 text-blue-400';
      case 'Order Pending':
        return 'border-amber-500/60 bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/40';
      case 'Bill Requested':
        return 'border-purple-500/60 bg-purple-500/15 text-purple-400 ring-1 ring-purple-500/40';
      case 'Cleaning':
        return 'border-zinc-500/40 bg-zinc-500/10 text-zinc-400';
      case 'Reserved':
        return 'border-rose-500/40 bg-rose-500/10 text-rose-400';
      default:
        return 'border-zinc-700 bg-zinc-800 text-zinc-300';
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
        <div>
          <h2 className="text-xl font-bold text-white">Floor & Table Management</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Real-time table occupancy, floor layout map, and cryptographic QR tokens
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={fetchTables}
            className="p-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition"
            title="Refresh tables"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 flex items-center space-x-1.5 transition"
          >
            <Plus className="w-4 h-4" />
            <span>Add Table</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        {/* Sections */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 scrollbar-none w-full sm:w-auto">
          {sections.map((sec) => (
            <button
              key={sec}
              onClick={() => setSelectedSection(sec)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition ${
                selectedSection === sec
                  ? 'bg-brand-500 text-white'
                  : 'bg-[#12131a] text-zinc-400 hover:text-white border border-zinc-800'
              }`}
            >
              {sec}
            </button>
          ))}
        </div>

        {/* Status Dropdown Filter */}
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-zinc-400">Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-[#12131a] border border-zinc-700 text-xs text-zinc-200"
          >
            <option value="All">All Statuses</option>
            {statusOptions.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Interactive Floor Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((n) => (
            <div key={n} className="h-44 bg-zinc-900 rounded-3xl animate-pulse"></div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4">
          {filteredTables.map((table) => {
            const statusBadge = getStatusColor(table.status);
            return (
              <div
                key={table.id}
                className="bg-[#12131a] border border-zinc-800/80 hover:border-zinc-700 rounded-3xl p-4 shadow-xl transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-lg font-black text-white">{table.table_number}</span>
                    <button
                      onClick={() => setQrModalTable(table)}
                      className="p-1.5 rounded-xl bg-zinc-800/80 hover:bg-zinc-700 text-amber-400 border border-zinc-700 transition"
                      title="View & Print Table QR Code"
                    >
                      <QrCode className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="flex items-center space-x-2 text-xs text-zinc-400 mb-3">
                    <span className="flex items-center space-x-1 font-medium">
                      <Users className="w-3.5 h-3.5 text-zinc-500" />
                      <span>{table.capacity} Seats</span>
                    </span>
                    <span className="text-zinc-600">•</span>
                    <span className="font-medium text-zinc-300">{table.section}</span>
                  </div>

                  {/* Active Order / Bill Amount */}
                  <div className="p-2.5 rounded-2xl bg-zinc-900 border border-zinc-800/80 mb-3 text-xs space-y-1">
                    <div className="flex justify-between text-zinc-400">
                      <span>Current Bill</span>
                      <span className="font-bold text-white">
                        {table.active_bill_amount ? `₹${table.active_bill_amount}` : 'None'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Status Switcher Dropdown */}
                <div>
                  <select
                    value={table.status}
                    onChange={(e) => handleStatusChange(table.id, e.target.value as TableStatus)}
                    className={`w-full px-3 py-1.5 rounded-xl border text-xs font-bold transition focus:outline-none ${statusBadge}`}
                  >
                    {statusOptions.map((opt) => (
                      <option key={opt} value={opt} className="bg-zinc-900 text-white font-normal">
                        {opt}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Table Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-[#181924] border border-zinc-700 rounded-3xl max-w-md w-full p-6 shadow-2xl relative">
            <button
              onClick={() => setShowAddModal(false)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-white mb-4">Add Restaurant Table</h3>

            <form onSubmit={handleCreateTable} className="space-y-4 text-xs">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Table Number / Identifier
                </label>
                <input
                  type="text"
                  required
                  value={newTableNum}
                  onChange={(e) => setNewTableNum(e.target.value)}
                  placeholder="e.g. T-11, Booth-04"
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Seating Capacity
                </label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  required
                  value={newCapacity}
                  onChange={(e) => setNewCapacity(parseInt(e.target.value, 10) || 2)}
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Floor Section
                </label>
                <select
                  value={newSection}
                  onChange={(e) => setNewSection(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-brand-500"
                >
                  <option value="Main Dining">Main Dining</option>
                  <option value="Terrace Garden">Terrace Garden</option>
                  <option value="Window Booth">Window Booth</option>
                  <option value="VIP Lounge">VIP Lounge</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 transition mt-2"
              >
                {isSubmitting ? 'Creating...' : 'Create Table'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* QR Code Standee Print Modal */}
      {qrModalTable && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-white text-zinc-900 rounded-3xl max-w-sm w-full p-6 shadow-2xl relative text-center">
            <button
              onClick={() => setQrModalTable(null)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-800 font-bold"
            >
              ✕
            </button>

            <span className="text-[10px] uppercase font-bold text-amber-600 tracking-wider block">
              The Royal Saffron
            </span>
            <h3 className="text-xl font-black tracking-tight mt-0.5">
              Table {qrModalTable.table_number}
            </h3>
            <p className="text-xs text-zinc-500 mt-1 mb-4">
              Scan to view digital menu & place direct orders
            </p>

            <div className="p-4 bg-zinc-50 border-2 border-dashed border-zinc-200 rounded-2xl inline-block shadow-inner mb-4">
              {qrModalTable.qr_token && (
                <QRCodeSVG
                  value={`${window.location.origin}/table/${qrModalTable.qr_token}`}
                  size={190}
                  level="H"
                  includeMargin={true}
                />
              )}
            </div>

            <p className="text-[10px] text-zinc-400 font-mono break-all mb-4">
              Token: {qrModalTable.qr_token?.slice(0, 24)}...
            </p>

            <div className="flex space-x-2">
              <a
                href={`${window.location.origin}/table/${qrModalTable.qr_token}`}
                target="_blank"
                rel="noreferrer"
                className="flex-1 py-2 rounded-xl bg-zinc-100 hover:bg-zinc-200 text-zinc-800 font-bold text-xs transition"
              >
                Open Customer View
              </a>
              <button
                onClick={() => window.print()}
                className="flex-1 py-2 rounded-xl bg-zinc-900 hover:bg-black text-white font-bold text-xs transition flex items-center justify-center space-x-1"
              >
                <Printer className="w-3.5 h-3.5" />
                <span>Print Standee</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

