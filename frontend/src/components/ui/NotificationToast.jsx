import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

const NotificationToastContext = createContext(null);

function ToastItem({ id, message, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(id), 5000);
    return () => clearTimeout(t);
  }, [id, message, onDismiss]);

  return (
    <div
      role="status"
      className="max-w-sm rounded border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 shadow"
    >
      {message}
    </div>
  );
}

export function NotificationToastProvider({ children }) {
  const [items, setItems] = useState([]);

  const addToast = useCallback((payload) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    setItems((prev) => [...prev, { id, message: payload?.message || 'New notification' }]);
  }, []);

  const removeToast = useCallback((id) => {
    setItems((prev) => prev.filter((x) => x.id !== id));
  }, []);

  return (
    <NotificationToastContext.Provider value={{ addToast }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
        {items.map((item) => (
          <div key={item.id} className="pointer-events-auto">
            <ToastItem id={item.id} message={item.message} onDismiss={removeToast} />
          </div>
        ))}
      </div>
    </NotificationToastContext.Provider>
  );
}

export function useNotificationToast() {
  const ctx = useContext(NotificationToastContext);
  if (!ctx) {
    throw new Error('useNotificationToast must be used within NotificationToastProvider');
  }
  return ctx;
}
