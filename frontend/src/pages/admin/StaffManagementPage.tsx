import React, { useState, useEffect } from 'react';
import { Users, Plus, ShieldCheck, Mail, Phone, Trash2, X } from 'lucide-react';
import { authApi } from '../../services/api';
import { User, UserRole } from '../../types';

export const StaffManagementPage: React.FC = () => {
  const [staffList, setStaffList] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  // New staff form
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [role, setRole] = useState<UserRole>('WAITER');
  const [submitting, setSubmitting] = useState(false);

  const fetchStaff = async () => {
    try {
      const data = await authApi.listStaff();
      setStaffList(data);
    } catch (err) {
      console.error('Failed to load staff list:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStaff();
  }, []);

  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await authApi.createStaff({
        full_name: fullName,
        email,
        username,
        password,
        phone_number: phone || undefined,
        role,
        restaurant_id: 1,
      });
      setShowModal(false);
      setFullName('');
      setEmail('');
      setUsername('');
      setPassword('');
      setPhone('');
      await fetchStaff();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to create staff member');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteStaff = async (staffId: number) => {
    if (!window.confirm('Are you sure you want to remove this staff account?')) return;
    try {
      await authApi.deleteStaff(staffId);
      await fetchStaff();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to delete staff member');
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
        <div>
          <h2 className="text-xl font-bold text-white">Staff & Role-Based Access</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Manage personnel, assign responsibilities, and control application privileges
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 flex items-center space-x-1.5 transition"
        >
          <Plus className="w-4 h-4" />
          <span>Add Staff Member</span>
        </button>
      </div>

      {/* Staff Table */}
      <div className="bg-[#12131a] border border-zinc-800 rounded-3xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-zinc-900/80 text-zinc-400 uppercase font-bold text-[10px] tracking-wider border-b border-zinc-800">
              <tr>
                <th className="px-6 py-4">Staff Member</th>
                <th className="px-6 py-4">Role & Access</th>
                <th className="px-6 py-4">Contact</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/80">
              {staffList.map((st) => (
                <tr key={st.id} className="hover:bg-zinc-800/30 transition">
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 rounded-full bg-brand-500/20 text-brand-400 font-bold flex items-center justify-center text-xs">
                        {st.full_name.charAt(0)}
                      </div>
                      <div>
                        <span className="font-bold text-white block">{st.full_name}</span>
                        <span className="text-[11px] text-zinc-500">@{st.username}</span>
                      </div>
                    </div>
                  </td>

                  <td className="px-6 py-4">
                    <span
                      className={`px-2.5 py-1 rounded-full text-[10px] font-bold border ${
                        st.role === 'ADMIN'
                          ? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
                          : st.role === 'MANAGER'
                          ? 'bg-blue-500/15 text-blue-400 border-blue-500/30'
                          : st.role === 'KITCHEN'
                          ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                          : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                      }`}
                    >
                      {st.role}
                    </span>
                  </td>

                  <td className="px-6 py-4 space-y-0.5 text-zinc-400">
                    <div className="flex items-center space-x-1.5">
                      <Mail className="w-3 h-3 text-zinc-500" />
                      <span>{st.email}</span>
                    </div>
                    {st.phone_number && (
                      <div className="flex items-center space-x-1.5">
                        <Phone className="w-3 h-3 text-zinc-500" />
                        <span>{st.phone_number}</span>
                      </div>
                    )}
                  </td>

                  <td className="px-6 py-4">
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-bold">
                      Active
                    </span>
                  </td>

                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => handleDeleteStaff(st.id)}
                      className="p-1.5 rounded-lg text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition"
                      title="Delete account"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Staff Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-[#181924] border border-zinc-700 rounded-3xl max-w-md w-full p-6 shadow-2xl relative text-xs">
            <button
              onClick={() => setShowModal(false)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-bold text-white mb-4">Add Staff Member</h3>

            <form onSubmit={handleCreateStaff} className="space-y-4">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Vikram Malhotra"
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Username
                </label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. vikram_m"
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Email Address
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="vikram@royalsaffron.com"
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                    Password
                  </label>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
                  />
                </div>

                <div>
                  <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                    Portal Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as UserRole)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
                  >
                    <option value="ADMIN">ADMIN</option>
                    <option value="MANAGER">MANAGER</option>
                    <option value="WAITER">WAITER</option>
                    <option value="KITCHEN">KITCHEN</option>
                    <option value="CASHIER">CASHIER</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 transition mt-2"
              >
                {submitting ? 'Creating...' : 'Create Account'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

