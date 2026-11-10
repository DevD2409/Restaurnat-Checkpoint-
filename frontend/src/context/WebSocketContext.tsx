import React, { createContext, useContext, useEffect, useState } from 'react';
import { wsService } from '../services/websocket';
import { useAuth } from './AuthContext';

interface WebSocketContextType {
  lastEvent: { type: string; data: any } | null;
  connectChannel: (channelOrPath: string, restaurantId?: number) => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lastEvent, setLastEvent] = useState<{ type: string; data: any } | null>(null);
  const { user } = useAuth();

  useEffect(() => {
    const unsubscribe = wsService.subscribe((event) => {
      setLastEvent(event);
    });
    return () => {
      unsubscribe();
    };
  }, []);

  const connectChannel = (channelOrPath: string, restaurantId?: number) => {
    const targetTenantId = restaurantId || user?.restaurant_id;
    let finalPath = channelOrPath;

    // Route staff channels to tenant-specific room if tenant context is available
    if (!channelOrPath.startsWith('tenant/') && !channelOrPath.startsWith('table/')) {
      if (targetTenantId) {
        finalPath = `tenant/${targetTenantId}/${channelOrPath}`;
      }
    } else if (channelOrPath.startsWith('table/') && targetTenantId) {
      const tableId = channelOrPath.replace('table/', '');
      finalPath = `tenant/${targetTenantId}/table/${tableId}`;
    }

    wsService.connect(finalPath);
  };

  return (
    <WebSocketContext.Provider value={{ lastEvent, connectChannel }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

