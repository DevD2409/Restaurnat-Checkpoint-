import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  wsService,
  ConnectOptions,
  WebSocketConnectionStatus,
} from '../services/websocket';
import { useAuth } from './AuthContext';

export interface ConnectChannelOptions {
  restaurantId?: number;
  sessionToken?: string | null;
  token?: string | null;
}

interface WebSocketContextType {
  lastEvent: { type: string; data: any } | null;
  connectionStatus: WebSocketConnectionStatus;
  authError: string | null;
  connectChannel: (
    channelOrPath: string,
    optionsOrRestaurantId?: number | ConnectChannelOptions
  ) => void;
  disconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lastEvent, setLastEvent] = useState<{ type: string; data: any } | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<WebSocketConnectionStatus>(
    wsService.getStatus()
  );
  const [authError, setAuthError] = useState<string | null>(wsService.getAuthError());
  const { user } = useAuth();

  useEffect(() => {
    const unsubEvents = wsService.subscribe((event) => {
      setLastEvent(event);
    });

    const unsubStatus = wsService.onStatusChange((status, err) => {
      setConnectionStatus(status);
      setAuthError(err);
    });

    return () => {
      unsubEvents();
      unsubStatus();
    };
  }, []);

  const connectChannel = (
    channelOrPath: string,
    optionsOrRestaurantId?: number | ConnectChannelOptions
  ) => {
    const options: ConnectChannelOptions =
      typeof optionsOrRestaurantId === 'number'
        ? { restaurantId: optionsOrRestaurantId }
        : optionsOrRestaurantId || {};

    // For authenticated staff, use the authenticated user's tenant ID.
    // Never trust an arbitrary browser-supplied restaurant_id for non-superadmin staff.
    const isSuperAdmin = user?.role === 'PLATFORM_SUPER_ADMIN';
    const targetTenantId = isSuperAdmin
      ? options.restaurantId || user?.restaurant_id
      : user?.restaurant_id || options.restaurantId;

    const cleanPath = channelOrPath.replace(/^\/+/, '');
    const isTableChannel = cleanPath.startsWith('table/') || cleanPath.includes('/table/');
    let finalPath = cleanPath;

    if (isTableChannel) {
      if (!cleanPath.startsWith('tenant/') && targetTenantId) {
        const tableId = cleanPath.replace(/^.*table\//, '');
        finalPath = `tenant/${targetTenantId}/table/${tableId}`;
      }
    } else if (!cleanPath.startsWith('tenant/') && targetTenantId) {
      finalPath = `tenant/${targetTenantId}/${cleanPath}`;
    }

    // Customer table session resolution
    let resolvedSessionToken: string | null | undefined = options.sessionToken;
    if (resolvedSessionToken === undefined && isTableChannel) {
      try {
        resolvedSessionToken = sessionStorage.getItem('smart_restaurant_session_token');
      } catch {
        resolvedSessionToken = null;
      }
    }

    // Staff JWT resolution: use authenticated user's token from localStorage
    let resolvedToken: string | null | undefined = options.token;
    if (resolvedToken === undefined && user) {
      try {
        resolvedToken = localStorage.getItem('token');
      } catch {
        resolvedToken = null;
      }
    }

    const wsOptions: ConnectOptions = {
      token: resolvedToken,
      sessionToken: resolvedSessionToken,
      restaurantId: targetTenantId,
    };

    wsService.connect(finalPath, wsOptions);
  };

  const disconnect = () => {
    wsService.disconnect();
  };

  return (
    <WebSocketContext.Provider
      value={{
        lastEvent,
        connectionStatus,
        authError,
        connectChannel,
        disconnect,
      }}
    >
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
