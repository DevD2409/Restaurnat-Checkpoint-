import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Search, Flame, Soup, Wheat, Coffee, IceCream, Plus, Minus,
  Sparkles, AlertCircle, ShoppingBag, Clock, Heart, Utensils,
  Check, X
} from 'lucide-react';
import { menuApi, tableApi } from '../../services/api';
import { useCart } from '../../context/CartContext';
import { MenuCategory, MenuItem, MenuCustomizationGroup } from '../../types';
import { resolveMediaUrl } from '../../config/runtime';

export const MenuPage: React.FC = () => {
  const { qrToken } = useParams<{ qrToken: string }>();
  const { setTableSession, addItem, items: cartItems, tableNumber } = useCart();

  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [vegFilter, setVegFilter] = useState<'all' | 'veg' | 'non-veg'>('all');
  const [loading, setLoading] = useState(true);
  const [qrValidating, setQrValidating] = useState(false);
  const [qrError, setQrError] = useState<string | null>(null);

  // Customization Modal State
  const [activeItemForCustomization, setActiveItemForCustomization] = useState<MenuItem | null>(null);
  const [selectedOptions, setSelectedOptions] = useState<{ [groupName: string]: string[] }>({});
  const [customizationQuantity, setCustomizationQuantity] = useState(1);
  const [customizationSpecialNotes, setCustomizationSpecialNotes] = useState('');

  // Validate QR token if provided in URL
  useEffect(() => {
    const validateToken = async () => {
      if (!qrToken) return;
      setQrValidating(true);
      try {
        const res = await tableApi.validateQR(qrToken);
        if (res.valid && res.table_id && res.table_number) {
          setTableSession(res.table_id, res.table_number, res.restaurant_id || 1);
        }
      } catch (err: any) {
        setQrError(err?.response?.data?.detail || 'Invalid or expired QR code.');
      } finally {
        setQrValidating(false);
      }
    };
    validateToken();
  }, [qrToken]);

  // Load Menu Categories and Items
  useEffect(() => {
    const fetchMenu = async () => {
      try {
        const data = await menuApi.getCategories();
        setCategories(data);
        if (data.length > 0) {
          setSelectedCategory(data[0].id);
        }
      } catch (err) {
        console.error('Failed to load menu:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchMenu();
  }, []);

  const openCustomizationModal = (item: MenuItem) => {
    setActiveItemForCustomization(item);
    setCustomizationQuantity(1);
    setCustomizationSpecialNotes('');

    // Pre-select defaults
    const defaults: { [groupName: string]: string[] } = {};
    item.customization_groups?.forEach((grp) => {
      const defaultOpts = grp.options.filter((o) => o.is_default).map((o) => o.name);
      defaults[grp.group_name] = defaultOpts.length > 0 ? defaultOpts : (grp.options.length > 0 ? [grp.options[0].name] : []);
    });
    setSelectedOptions(defaults);
  };

  const handleOptionToggle = (group: MenuCustomizationGroup, optionName: string) => {
    const current = selectedOptions[group.group_name] || [];
    if (group.max_select === 1) {
      setSelectedOptions({ ...selectedOptions, [group.group_name]: [optionName] });
    } else {
      if (current.includes(optionName)) {
        setSelectedOptions({
          ...selectedOptions,
          [group.group_name]: current.filter((name) => name !== optionName),
        });
      } else {
        if (current.length < group.max_select) {
          setSelectedOptions({
            ...selectedOptions,
            [group.group_name]: [...current, optionName],
          });
        }
      }
    }
  };

  const handleAddToCartFromModal = () => {
    if (!activeItemForCustomization) return;

    const flattenedCustomizations: { group_name: string; option_name: string; additional_price: number }[] = [];
    activeItemForCustomization.customization_groups?.forEach((grp) => {
      const chosen = selectedOptions[grp.group_name] || [];
      chosen.forEach((optName) => {
        const optObj = grp.options.find((o) => o.name === optName);
        flattenedCustomizations.push({
          group_name: grp.group_name,
          option_name: optName,
          additional_price: optObj ? optObj.additional_price : 0,
        });
      });
    });

    addItem({
      menu_item_id: activeItemForCustomization.id,
      name: activeItemForCustomization.name,
      unit_price: activeItemForCustomization.price,
      quantity: customizationQuantity,
      is_veg: activeItemForCustomization.is_veg,
      selected_customizations: flattenedCustomizations,
      special_instructions: customizationSpecialNotes.trim() || undefined,
      image_url: activeItemForCustomization.image_url,
    });

    setActiveItemForCustomization(null);
  };

  const handleQuickAdd = (dish: MenuItem) => {
    if (dish.customization_groups && dish.customization_groups.length > 0) {
      openCustomizationModal(dish);
    } else {
      addItem({
        menu_item_id: dish.id,
        name: dish.name,
        unit_price: dish.price,
        quantity: 1,
        is_veg: dish.is_veg,
        selected_customizations: [],
        image_url: dish.image_url,
      });
    }
  };

  // Filtered Items Calculation
  const currentCategoryObj = categories.find((c) => c.id === selectedCategory);
  const itemsToDisplay = (currentCategoryObj ? currentCategoryObj.items : []).filter((item) => {
    if (vegFilter === 'veg' && !item.is_veg) return false;
    if (vegFilter === 'non-veg' && item.is_veg) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = item.name.toLowerCase().includes(q);
      const matchDesc = item.description?.toLowerCase().includes(q);
      if (!matchName && !matchDesc) return false;
    }
    return true;
  });

  const getCategoryIcon = (iconName: string) => {
    switch (iconName) {
      case 'Flame': return <Flame className="w-4 h-4" />;
      case 'Soup': return <Soup className="w-4 h-4" />;
      case 'Wheat': return <Wheat className="w-4 h-4" />;
      case 'Coffee': return <Coffee className="w-4 h-4" />;
      case 'IceCream': return <IceCream className="w-4 h-4" />;
      default: return <Sparkles className="w-4 h-4" />;
    }
  };

  // Safe fallback placeholder for culinary image errors
  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement, Event>) => {
    const target = e.currentTarget;
    target.onerror = null; // Prevent loop
    target.src = 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500&auto=format&fit=crop&q=60';
  };

  return (
    <div className="space-y-5 animate-fade-in pb-16">
      {/* QR Banner / Validation Error */}
      {qrValidating && (
        <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-2xl text-xs text-amber-400 flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
          <span>Validating digital table session...</span>
        </div>
      )}

      {qrError && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-2xl text-xs text-red-400 flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{qrError}</span>
        </div>
      )}

      {/* Hero Welcome & Search Banner */}
      <div className="relative rounded-3xl overflow-hidden bg-gradient-to-r from-zinc-900 via-[#161722] to-[#181924] border border-zinc-800 p-5 shadow-xl">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-brand-400 text-xs font-bold uppercase tracking-wider mb-1">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Smart QR Dining Experience</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight">
              Artisanal Cuisine & Culinary Craft
            </h2>
            <p className="text-xs text-zinc-400 mt-1 max-w-lg leading-relaxed">
              Explore freshly prepared gourmet delights. Customize dishes and place orders directly from your table.
            </p>
          </div>

          {/* Quick Dietary Filters */}
          <div className="flex items-center bg-zinc-900/90 p-1 rounded-2xl border border-zinc-700/60 self-stretch sm:self-auto">
            <button
              onClick={() => setVegFilter('all')}
              className={`flex-1 sm:flex-initial px-3.5 py-1.5 rounded-xl text-xs font-bold transition ${
                vegFilter === 'all' ? 'bg-zinc-700 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setVegFilter('veg')}
              className={`flex-1 sm:flex-initial px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 transition ${
                vegFilter === 'veg' ? 'bg-emerald-600 text-white shadow-sm' : 'text-emerald-400 hover:text-emerald-300'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 border border-white"></span>
              <span>Veg</span>
            </button>
            <button
              onClick={() => setVegFilter('non-veg')}
              className={`flex-1 sm:flex-initial px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 transition ${
                vegFilter === 'non-veg' ? 'bg-red-700 text-white shadow-sm' : 'text-red-400 hover:text-red-300'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-red-400 border border-white"></span>
              <span>Non-Veg</span>
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="mt-4 relative">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-zinc-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search dishes, ingredients or dietary tags..."
            className="w-full pl-10 pr-4 py-2.5 rounded-2xl bg-zinc-900/90 border border-zinc-700 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-brand-500 transition shadow-inner"
          />
        </div>
      </div>

      {/* Category Horizontal Scrolling Tabs */}
      <div className="relative">
        <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
          {categories.map((category) => {
            const isSelected = selectedCategory === category.id;
            return (
              <button
                key={category.id}
                onClick={() => setSelectedCategory(category.id)}
                className={`flex items-center space-x-2 px-4 py-2.5 rounded-2xl whitespace-nowrap text-xs font-bold border transition ${
                  isSelected
                    ? 'bg-brand-500 text-white border-brand-400 shadow-lg shadow-brand-500/25'
                    : 'bg-[#12131a] text-zinc-400 border-zinc-800 hover:border-zinc-700 hover:text-zinc-200'
                }`}
              >
                {getCategoryIcon(category.icon)}
                <span>{category.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Dishes Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="h-44 bg-zinc-900/50 rounded-3xl animate-pulse border border-zinc-800"></div>
          ))}
        </div>
      ) : itemsToDisplay.length === 0 ? (
        <div className="p-12 text-center bg-[#12131a] rounded-3xl border border-zinc-800">
          <Utensils className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <h4 className="text-base font-semibold text-zinc-300">No dishes found</h4>
          <p className="text-xs text-zinc-500 mt-1">Try adjusting your dietary filters or search keywords.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {itemsToDisplay.map((dish) => {
            const hasCustomizations = dish.customization_groups && dish.customization_groups.length > 0;
            return (
              <div
                key={dish.id}
                className="group bg-[#12131a] border border-zinc-800/80 hover:border-zinc-700/80 rounded-3xl overflow-hidden shadow-lg transition-all duration-300 flex flex-col justify-between"
              >
                <div className="p-4 flex gap-3 sm:gap-4 items-start">
                  {/* Left: Dish Details */}
                  <div className="flex-1 flex flex-col justify-between min-w-0">
                    <div>
                      {/* Dietary Badges & Tags */}
                      <div className="flex items-center space-x-2 mb-1.5">
                        <span
                          className={`w-3.5 h-3.5 rounded-sm flex items-center justify-center border ${
                            dish.is_veg
                              ? 'border-emerald-500 bg-emerald-500/10'
                              : 'border-red-500 bg-red-500/10'
                          }`}
                          title={dish.is_veg ? 'Vegetarian' : 'Non-Vegetarian'}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              dish.is_veg ? 'bg-emerald-500' : 'bg-red-500'
                            }`}
                          ></span>
                        </span>

                        {dish.is_bestseller && (
                          <span className="px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-[10px] font-bold text-amber-400">
                            ★ Bestseller
                          </span>
                        )}

                        {dish.spice_level && dish.spice_level !== 'Mild' && (
                          <span className="text-[10px] text-zinc-400 font-medium">
                            🌶️ {dish.spice_level}
                          </span>
                        )}
                      </div>

                      <h3 className="font-bold text-sm sm:text-base text-zinc-100 group-hover:text-brand-400 transition leading-snug truncate">
                        {dish.name}
                      </h3>

                      <p className="text-xs text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                        {dish.description}
                      </p>
                    </div>

                    {/* Price and Add/Custom Button Inline */}
                    <div className="mt-3 flex items-center justify-between pt-1">
                      <div className="flex items-baseline space-x-1.5">
                        <span className="text-base font-extrabold text-white">₹{dish.price}</span>
                        {dish.preparation_time && (
                          <span className="text-[10px] text-zinc-500 flex items-center space-x-0.5">
                            <Clock className="w-3 h-3 inline" />
                            <span>{dish.preparation_time}m</span>
                          </span>
                        )}
                      </div>

                      <button
                        onClick={() => handleQuickAdd(dish)}
                        className="px-3.5 py-1.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-md shadow-brand-500/25 border border-brand-400 flex items-center space-x-1 transition active:scale-95"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>{hasCustomizations ? 'Custom' : 'Add'}</span>
                      </button>
                    </div>
                  </div>

                  {/* Right: Clean Dish Thumbnail */}
                  <div className="relative w-24 h-24 sm:w-28 sm:h-28 flex-shrink-0 rounded-2xl overflow-hidden border border-zinc-800 bg-zinc-900">
                    <img
                      src={resolveMediaUrl(dish.image_url) || 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500&auto=format&fit=crop&q=60'}
                      alt={dish.name}
                      onError={handleImageError}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      loading="lazy"
                    />
                  </div>
                </div>

                {hasCustomizations && (
                  <div className="px-4 py-1.5 bg-zinc-900/60 border-t border-zinc-800/70 text-[10px] text-zinc-400 flex items-center justify-between">
                    <span className="text-amber-400/90 font-medium">✨ Customizable options</span>
                    <button
                      onClick={() => openCustomizationModal(dish)}
                      className="text-brand-400 hover:text-brand-300 font-bold"
                    >
                      Customize &gt;
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Floating Bottom Cart Bar */}
      {cartItems.length > 0 && (
        <div className="fixed bottom-16 md:bottom-6 left-4 right-4 z-30 max-w-md mx-auto animate-slide-up">
          <Link
            to={qrToken ? `/table/${qrToken}/cart` : '/menu/cart'}
            className="flex items-center justify-between px-4 py-3 rounded-2xl bg-gradient-to-r from-brand-600 to-amber-600 text-white shadow-2xl shadow-brand-500/30 border border-brand-400/50"
          >
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-xl bg-black/25 flex items-center justify-center font-extrabold text-xs">
                {cartItems.reduce((acc, i) => acc + i.quantity, 0)}
              </div>
              <div>
                <span className="text-xs font-bold block leading-tight">View Your Cart</span>
                <span className="text-[10px] text-amber-100">Review items & checkout</span>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <span className="text-sm font-extrabold">
                ₹{cartItems.reduce((sum, i) => sum + i.unit_price * i.quantity, 0)}
              </span>
              <span className="text-xs font-bold px-2 py-1 rounded-lg bg-black/25">
                Continue →
              </span>
            </div>
          </Link>
        </div>
      )}

      {/* Interactive Customization Bottom Sheet / Modal */}
      {activeItemForCustomization && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/75 backdrop-blur-sm p-0 sm:p-4 animate-fade-in">
          <div className="bg-[#181924] border border-zinc-700/80 rounded-t-3xl sm:rounded-3xl max-w-lg w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-slide-up sm:animate-fade-in">
            {/* Header */}
            <div className="p-4 sm:p-5 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-base text-white">
                  Customize {activeItemForCustomization.name}
                </h3>
                <span className="text-xs text-brand-400 font-bold">
                  Base Price: ₹{activeItemForCustomization.price}
                </span>
              </div>
              <button
                onClick={() => setActiveItemForCustomization(null)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-white bg-zinc-800/60"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Customization Options Body */}
            <div className="p-4 sm:p-5 space-y-5 overflow-y-auto flex-1">
              {activeItemForCustomization.customization_groups?.map((group) => (
                <div key={group.group_name} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-zinc-200">
                      {group.group_name}
                    </span>
                    <span className="text-[10px] text-zinc-400 font-semibold">
                      {group.max_select === 1 ? 'Choose 1' : `Max ${group.max_select}`}
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    {group.options.map((option) => {
                      const isChecked = (selectedOptions[group.group_name] || []).includes(option.name);
                      return (
                        <button
                          key={option.name}
                          type="button"
                          onClick={() => handleOptionToggle(group, option.name)}
                          className={`w-full p-3 rounded-2xl border text-xs flex items-center justify-between transition ${
                            isChecked
                              ? 'bg-brand-500/15 border-brand-500/50 text-white'
                              : 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-700'
                          }`}
                        >
                          <div className="flex items-center space-x-2.5">
                            <div
                              className={`w-4 h-4 rounded-md border flex items-center justify-center ${
                                isChecked
                                  ? 'bg-brand-500 border-brand-400 text-white'
                                  : 'border-zinc-600 bg-zinc-800'
                              }`}
                            >
                              {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                            </div>
                            <span className="font-medium">{option.name}</span>
                          </div>

                          <span className="font-bold text-brand-400">
                            {option.additional_price > 0 ? `+₹${option.additional_price}` : 'Free'}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}

              {/* Special Instructions */}
              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  Chef Preparation Instructions
                </label>
                <input
                  type="text"
                  value={customizationSpecialNotes}
                  onChange={(e) => setCustomizationSpecialNotes(e.target.value)}
                  placeholder="e.g. Extra crispy, less oil, sauce on side"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 sm:p-5 border-t border-zinc-800 bg-zinc-900/60 flex items-center justify-between gap-3">
              <div className="flex items-center space-x-3 bg-zinc-900 px-3 py-1.5 rounded-xl border border-zinc-700">
                <button
                  type="button"
                  onClick={() => setCustomizationQuantity(Math.max(1, customizationQuantity - 1))}
                  className="text-zinc-400 hover:text-white p-1"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
                <span className="text-xs font-bold text-white px-1">
                  {customizationQuantity}
                </span>
                <button
                  type="button"
                  onClick={() => setCustomizationQuantity(customizationQuantity + 1)}
                  className="text-zinc-400 hover:text-white p-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>

              <button
                onClick={handleAddToCartFromModal}
                className="flex-1 py-3 px-4 rounded-xl bg-gradient-to-r from-brand-600 to-amber-600 text-white font-bold text-xs shadow-lg shadow-brand-500/25 flex items-center justify-center space-x-1.5 transition active:scale-95"
              >
                <span>Add to Cart</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
