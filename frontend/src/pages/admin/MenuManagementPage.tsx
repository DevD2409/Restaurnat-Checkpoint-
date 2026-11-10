import React, { useState, useEffect } from 'react';
import {
  UtensilsCrossed, Plus, Edit, Trash2, Check,
  AlertCircle, Sparkles, Flame, ToggleLeft, ToggleRight, X
} from 'lucide-react';
import { menuApi } from '../../services/api';
import { MenuCategory, MenuItem } from '../../types';

export const MenuManagementPage: React.FC = () => {
  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [selectedCatId, setSelectedCatId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // Modals
  const [showItemModal, setShowItemModal] = useState(false);
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);

  // Form Fields
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formPrice, setFormPrice] = useState(250);
  const [formIsVeg, setFormIsVeg] = useState(true);
  const [formIsBestseller, setFormIsBestseller] = useState(false);
  const [formPrepTime, setFormPrepTime] = useState(15);
  const [formImgUrl, setFormImgUrl] = useState('');
  const [formSpice, setFormSpice] = useState<'Mild' | 'Medium' | 'Hot' | 'Extra Hot'>('Medium');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchCategories = async () => {
    try {
      const data = await menuApi.getCategories(true);
      setCategories(data);
      if (data.length > 0 && !selectedCatId) {
        setSelectedCatId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load menu categories:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCategories();
  }, []);

  const handleOpenAddModal = () => {
    setEditingItem(null);
    setFormName('');
    setFormDesc('');
    setFormPrice(250);
    setFormIsVeg(true);
    setFormIsBestseller(false);
    setFormPrepTime(15);
    setFormImgUrl('');
    setFormSpice('Medium');
    setShowItemModal(true);
  };

  const handleOpenEditModal = (item: MenuItem) => {
    setEditingItem(item);
    setFormName(item.name);
    setFormDesc(item.description || '');
    setFormPrice(item.price);
    setFormIsVeg(item.is_veg);
    setFormIsBestseller(item.is_bestseller);
    setFormPrepTime(item.preparation_time);
    setFormImgUrl(item.image_url || '');
    setFormSpice(item.spice_level || 'Medium');
    setShowItemModal(true);
  };

  const handleSaveItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCatId) return;
    setIsSubmitting(true);

    try {
      if (editingItem) {
        await menuApi.updateItem(editingItem.id, {
          name: formName,
          description: formDesc,
          price: formPrice,
          is_veg: formIsVeg,
          is_bestseller: formIsBestseller,
          preparation_time: formPrepTime,
          image_url: formImgUrl || undefined,
          spice_level: formSpice,
        });
      } else {
        await menuApi.createItem({
          category_id: selectedCatId,
          name: formName,
          description: formDesc,
          price: formPrice,
          is_veg: formIsVeg,
          is_bestseller: formIsBestseller,
          is_available: true,
          preparation_time: formPrepTime,
          image_url: formImgUrl || undefined,
          spice_level: formSpice,
        });
      }
      setShowItemModal(false);
      await fetchCategories();
    } catch (err) {
      alert('Failed to save menu item');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleAvailability = async (itemId: number) => {
    try {
      await menuApi.toggleAvailability(itemId);
      await fetchCategories();
    } catch (err) {
      alert('Failed to toggle availability');
    }
  };

  const handleDeleteItem = async (itemId: number) => {
    if (!window.confirm('Are you sure you want to delete this menu item?')) return;
    try {
      await menuApi.deleteItem(itemId);
      await fetchCategories();
    } catch (err) {
      alert('Failed to delete menu item');
    }
  };

  const currentCat = categories.find((c) => c.id === selectedCatId);

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#12131a] border border-zinc-800 rounded-3xl p-5 shadow-xl">
        <div>
          <h2 className="text-xl font-bold text-white">Menu & Dish Management</h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Configure recipes, prices, dietary classifications, and 1-click availability
          </p>
        </div>

        <button
          onClick={handleOpenAddModal}
          className="px-4 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 flex items-center space-x-1.5 transition"
        >
          <Plus className="w-4 h-4" />
          <span>Add New Dish</span>
        </button>
      </div>

      {/* Category Tabs */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setSelectedCatId(cat.id)}
            className={`px-4 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition ${
              selectedCatId === cat.id
                ? 'bg-brand-500 text-white shadow-md shadow-brand-500/20'
                : 'bg-[#12131a] text-zinc-400 hover:text-white border border-zinc-800'
            }`}
          >
            {cat.name} ({cat.items?.length || 0})
          </button>
        ))}
      </div>

      {/* Items Table / Cards */}
      {loading ? (
        <div className="py-12 text-center text-xs text-zinc-500">Loading dishes...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {currentCat?.items?.map((item) => (
            <div
              key={item.id}
              className={`bg-[#12131a] border rounded-3xl p-4 shadow-xl transition flex flex-col justify-between ${
                item.is_available ? 'border-zinc-800/80 hover:border-zinc-700' : 'border-zinc-800 opacity-60'
              }`}
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`w-3 h-3 rounded-sm flex items-center justify-center border ${
                        item.is_veg ? 'border-emerald-500' : 'border-red-500'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${item.is_veg ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
                    </span>
                    <h4 className="font-bold text-sm text-white">{item.name}</h4>
                  </div>

                  <span className="text-sm font-extrabold text-brand-400">₹{item.price}</span>
                </div>

                <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed mb-3">
                  {item.description || 'No description provided.'}
                </p>

                <div className="flex items-center space-x-2 text-[10px] text-zinc-400 mb-3">
                  {item.is_bestseller && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 font-bold border border-amber-500/30">
                      ★ Bestseller
                    </span>
                  )}
                  <span>⏱️ {item.preparation_time}m prep</span>
                  <span>🌶️ {item.spice_level}</span>
                </div>
              </div>

              {/* Actions Footer */}
              <div className="pt-3 border-t border-zinc-800/80 flex items-center justify-between">
                <button
                  onClick={() => handleToggleAvailability(item.id)}
                  className={`text-xs font-semibold px-2.5 py-1 rounded-lg border transition ${
                    item.is_available
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                      : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                  }`}
                >
                  {item.is_available ? 'In Stock' : 'Sold Out'}
                </button>

                <div className="flex items-center space-x-1.5">
                  <button
                    onClick={() => handleOpenEditModal(item)}
                    className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white transition"
                    title="Edit dish"
                  >
                    <Edit className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDeleteItem(item.id)}
                    className="p-1.5 rounded-lg bg-zinc-800 hover:bg-red-500/20 text-zinc-400 hover:text-red-400 transition"
                    title="Delete dish"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add / Edit Dish Modal */}
      {showItemModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-[#181924] border border-zinc-700 rounded-3xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl relative text-xs">
            <button
              onClick={() => setShowItemModal(false)}
              className="absolute top-4 right-4 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-bold text-white mb-4">
              {editingItem ? `Edit ${editingItem.name}` : 'Add New Menu Dish'}
            </h3>

            <form onSubmit={handleSaveItem} className="space-y-4">
              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Dish Name
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Saffron Dum Biryani"
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Description
                </label>
                <textarea
                  rows={2}
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="Detailed culinary description and marinade notes..."
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-brand-500"
                ></textarea>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                    Price (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formPrice}
                    onChange={(e) => setFormPrice(parseFloat(e.target.value) || 0)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                    Prep Time (Minutes)
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={formPrepTime}
                    onChange={(e) => setFormPrepTime(parseInt(e.target.value, 10) || 15)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                    Dietary Classification
                  </label>
                  <select
                    value={formIsVeg ? 'veg' : 'non-veg'}
                    onChange={(e) => setFormIsVeg(e.target.value === 'veg')}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
                  >
                    <option value="veg">🌱 Pure Vegetarian</option>
                    <option value="non-veg">🍗 Non-Vegetarian</option>
                  </select>
                </div>

                <div>
                  <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                    Spice Level
                  </label>
                  <select
                    value={formSpice}
                    onChange={(e) => setFormSpice(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white"
                  >
                    <option value="Mild">Mild</option>
                    <option value="Medium">Medium</option>
                    <option value="Hot">Hot</option>
                    <option value="Extra Hot">Extra Hot</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-zinc-300 font-semibold mb-1 uppercase tracking-wider text-[10px]">
                  Food Photo URL
                </label>
                <input
                  type="url"
                  value={formImgUrl}
                  onChange={(e) => setFormImgUrl(e.target.value)}
                  placeholder="https://images.unsplash.com/..."
                  className="w-full px-3 py-2 rounded-xl bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="bestsellerCheck"
                  checked={formIsBestseller}
                  onChange={(e) => setFormIsBestseller(e.target.checked)}
                  className="rounded bg-zinc-900 border-zinc-700 text-brand-500 focus:ring-brand-500"
                />
                <label htmlFor="bestsellerCheck" className="text-zinc-300 font-medium">
                  Mark as Chef's Bestseller
                </label>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 transition mt-2"
              >
                {isSubmitting ? 'Saving...' : 'Save Dish'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

