import React, { createContext, useContext, useState, useEffect } from 'react';
import { CartItem } from '../types';

interface CartContextType {
  items: CartItem[];
  tableId: number | null;
  tableNumber: string | null;
  restaurantId: number;
  sessionToken: string | null;
  customerName: string;
  tipAmount: number;
  orderInstructions: string;
  subtotal: number;
  taxAmount: number;
  serviceCharge: number;
  totalAmount: number;
  setTableSession: (
    tableId: number,
    tableNumber: string,
    restaurantId?: number,
    sessionToken?: string | null
  ) => void;
  clearTableSession: () => void;
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
    try {
      const saved = localStorage.getItem('smart_restaurant_cart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [tableId, setTableId] = useState<number | null>(() => {
    try {
      const saved = localStorage.getItem('smart_restaurant_table_id');
      return saved ? parseInt(saved, 10) : null;
    } catch {
      return null;
    }
  });
  const [tableNumber, setTableNumber] = useState<string | null>(() => {
    try {
      return localStorage.getItem('smart_restaurant_table_number') || null;
    } catch {
      return null;
    }
  });
  const [sessionToken, setSessionToken] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem('smart_restaurant_session_token') || null;
    } catch {
      return null;
    }
  });
  const [restaurantId, setRestaurantId] = useState<number>(1);
  const [customerName, setCustomerName] = useState<string>('Guest');
  const [tipAmount, setTipAmount] = useState<number>(0);
  const [orderInstructions, setOrderInstructions] = useState<string>('');

  useEffect(() => {
    try {
      localStorage.setItem('smart_restaurant_cart', JSON.stringify(items));
    } catch {
      // storage unavailable
    }
  }, [items]);

  const setTableSession = (
    tId: number,
    tNum: string,
    rId: number = 1,
    sToken?: string | null
  ) => {
    setTableId(tId);
    setTableNumber(tNum);
    setRestaurantId(rId);
    try {
      localStorage.setItem('smart_restaurant_table_id', tId.toString());
      localStorage.setItem('smart_restaurant_table_number', tNum);
      if (sToken) {
        setSessionToken(sToken);
        sessionStorage.setItem('smart_restaurant_session_token', sToken);
      }
    } catch {
      // storage unavailable
    }
  };

  const clearTableSession = () => {
    setTableId(null);
    setTableNumber(null);
    setSessionToken(null);
    try {
      localStorage.removeItem('smart_restaurant_table_id');
      localStorage.removeItem('smart_restaurant_table_number');
      sessionStorage.removeItem('smart_restaurant_session_token');
      localStorage.removeItem('smart_restaurant_session_token');
    } catch {
      // storage unavailable
    }
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
    try {
      localStorage.removeItem('smart_restaurant_cart');
    } catch {
      // storage unavailable
    }
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
        sessionToken,
        customerName,
        tipAmount,
        orderInstructions,
        subtotal,
        taxAmount,
        serviceCharge,
        totalAmount,
        setTableSession,
        clearTableSession,
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
