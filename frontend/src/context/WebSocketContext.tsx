import React, { createContext, useContext, useEffect, useState } from 'react';
import { wsService } from '../services/websocket';

interface WebSocketContextType {
  lastEvent: { type: string; data: any } | null;
  connectChannel: (channelOrPath: string) => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lastEvent, setLastEvent] = useState<{ type: string; data: any } | null>(null);

  useEffect(() => {
    const unsubscribe = wsService.subscribe((event) => {
      setLastEvent(event);
    });
    return () => {
      unsubscribe();
    };
  }, []);

  const connectChannel = (channelOrPath: string) => {
    wsService.connect(channelOrPath);
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

