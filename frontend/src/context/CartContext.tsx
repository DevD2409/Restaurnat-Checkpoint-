import React, { createContext, useContext, useState, useEffect } from 'react';
import { CartItem, OrderItemCustomization } from '../types';

interface CartContextType {
  items: CartItem[];
  tableId: number | null;
  tableNumber: string | null;
  restaurantId: number;
  customerName: string;
  tipAmount: number;
  orderInstructions: string;
  subtotal: number;
  taxAmount: number;
  serviceCharge: number;
  totalAmount: number;
  setTableSession: (tableId: number, tableNumber: string, restaurantId?: number) => void;
  setCustomerName: (name: string) => void;
  setTipAmount: (amount: number) => void;
  setOrderInstructions: (instructions: string) => void;
  addItem: (item: Omit<CartItem, 'id'>) => void;
  updateQuantity: (id: string, delta: number) => void;
  removeItem: (id: string) => void;
  clearCart: () => void;
  totalItemCount: number;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<CartItem[]>(() => {
    const saved = localStorage.getItem('smart_restaurant_cart');
    return saved ? JSON.parse(saved) : [];
  });
  const [tableId, setTableId] = useState<number | null>(() => {
    const saved = localStorage.getItem('smart_restaurant_table_id');
    return saved ? parseInt(saved, 10) : null;
  });
  const [tableNumber, setTableNumber] = useState<string | null>(() => {
    return localStorage.getItem('smart_restaurant_table_number') || null;
  });
  const [restaurantId, setRestaurantId] = useState<number>(1);
  const [customerName, setCustomerName] = useState<string>('Guest');
  const [tipAmount, setTipAmount] = useState<number>(0);
  const [orderInstructions, setOrderInstructions] = useState<string>('');

  useEffect(() => {
    localStorage.setItem('smart_restaurant_cart', JSON.stringify(items));
  }, [items]);

  const setTableSession = (tId: number, tNum: string, rId: number = 1) => {
    setTableId(tId);
    setTableNumber(tNum);
    setRestaurantId(rId);
    localStorage.setItem('smart_restaurant_table_id', tId.toString());
    localStorage.setItem('smart_restaurant_table_number', tNum);
  };

  const addItem = (itemData: Omit<CartItem, 'id'>) => {
    const customKey = itemData.selected_customizations
      .map((c) => `${c.group_name}:${c.option_name}`)
      .sort()
      .join('|');
    const compositeId = `${itemData.menu_item_id}_${customKey}`;

    setItems((prev) => {
      const existing = prev.find((i) => i.id === compositeId);
      if (existing) {
        return prev.map((i) =>
          i.id === compositeId ? { ...i, quantity: i.quantity + itemData.quantity } : i
        );
      }
      return [...prev, { ...itemData, id: compositeId }];
    });
  };

  const updateQuantity = (id: string, delta: number) => {
    setItems((prev) =>
      prev
        .map((i) => {
          if (i.id === id) {
            const newQty = i.quantity + delta;
            return newQty > 0 ? { ...i, quantity: newQty } : null;
          }
          return i;
        })
        .filter(Boolean) as CartItem[]
    );
  };

  const removeItem = (id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
  };

  const clearCart = () => {
    setItems([]);
    setOrderInstructions('');
    setTipAmount(0);
    localStorage.removeItem('smart_restaurant_cart');
  };

  const totalItemCount = items.reduce((acc, curr) => acc + curr.quantity, 0);

  const subtotal = items.reduce((sum, item) => {
    const addons = item.selected_customizations.reduce((acc, c) => acc + c.additional_price, 0);
    return sum + (item.unit_price + addons) * item.quantity;
  }, 0);

  const taxAmount = Math.round(subtotal * 0.05 * 100) / 100; // 5% GST
  const serviceCharge = Math.round(subtotal * 0.05 * 100) / 100; // 5% Service Charge
  const totalAmount = Math.round((subtotal + taxAmount + serviceCharge + tipAmount) * 100) / 100;

  return (
    <CartContext.Provider
      value={{
        items,
        tableId,
        tableNumber,
        restaurantId,
        customerName,
        tipAmount,
        orderInstructions,
        subtotal,
        taxAmount,
        serviceCharge,
        totalAmount,
        setTableSession,
        setCustomerName,
        setTipAmount,
        setOrderInstructions,
        addItem,
        updateQuantity,
        removeItem,
        clearCart,
        totalItemCount,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
};

