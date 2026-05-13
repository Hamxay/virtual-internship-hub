import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNotificationToast } from '../components/ui/NotificationToast';
import { getNotifications, markAsRead as markAsReadApi, markAllAsRead as markAllAsReadApi } from '../api/notifications.api';
import { API_BASE_URL } from '../api/client';

// Backend may send is_read as bool, string, or 0/1 — coerce for the bell UI.
function normalizeNotification(n) {
  if (n == null || typeof n !== 'object') return n;
  const read = n.is_read === true || n.is_read === 'true' || n.is_read === 1;
  return { ...n, is_read: read };
}

function buildNotificationsWsUrl(token) {
  const base = API_BASE_URL || 'http://localhost:8000/api';
  try {
    const u = new URL(base);
    const wsProto = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProto}//${u.host}/ws/notifications/?token=${encodeURIComponent(token)}`;
  } catch {
    return `ws://localhost:8000/ws/notifications/?token=${encodeURIComponent(token)}`;
  }
}

/** Live WS feed plus REST history for student/mentor dashboards. */
export function useLiveNotifications({ enabled }) {
  const { addToast } = useNotificationToast();
  const { isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const unreadCount = useMemo(
    () => notifications.filter((n) => n && n.is_read !== true).length,
    [notifications],
  );
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const allowReconnectRef = useRef(true);

  const loadHistory = useCallback(async () => {
    try {
      const list = await getNotifications();
      const raw = Array.isArray(list) ? list : [];
      setNotifications(raw.map(normalizeNotification));
    } catch {
      setNotifications([]);
    }
  }, []);

  useEffect(() => {
    if (!enabled || !isAuthenticated) {
      setNotifications([]);
      return undefined;
    }

    allowReconnectRef.current = true;
    loadHistory();

    const clearReconnect = () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      const token = localStorage.getItem('access_token');
      if (!token || !allowReconnectRef.current) return;

      clearReconnect();
      try {
        const ws = new WebSocket(buildNotificationsWsUrl(token));
        wsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            if (payload == null || typeof payload !== 'object') return;
            setNotifications((prev) => {
              const id = payload.id;
              const row = normalizeNotification(payload);
              return [row, ...prev.filter((entry) => entry.id !== id)];
            });
            if (!normalizeNotification(payload).is_read) {
              addToast({ message: payload.message || 'New notification' });
            }
          } catch {
            /* ignore malformed payloads */
          }
        };

        ws.onclose = () => {
          wsRef.current = null;
          if (!allowReconnectRef.current) return;
          if (!localStorage.getItem('access_token')) return;
          reconnectTimerRef.current = setTimeout(() => {
            if (allowReconnectRef.current && localStorage.getItem('access_token')) {
              connect();
            }
          }, 3000);
        };

        ws.onerror = () => {
          /* rely on onclose for reconnect */
        };
      } catch {
        /* ignore */
      }
    };

    connect();

    return () => {
      allowReconnectRef.current = false;
      clearReconnect();
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          /* ignore */
        }
        wsRef.current = null;
      }
    };
  }, [enabled, isAuthenticated, loadHistory, addToast]);

  const markAsRead = useCallback(async (id) => {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    try {
      await markAsReadApi(id);
    } catch {
      await loadHistory();
    }
  }, [loadHistory]);

  const markAllAsRead = useCallback(async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    try {
      await markAllAsReadApi();
    } catch {
      /* server may have failed — resync */
    } finally {
      await loadHistory();
    }
  }, [loadHistory]);

  return {
    notifications,
    unreadCount,
    dropdownOpen,
    setDropdownOpen,
    markAsRead,
    markAllAsRead,
    refreshNotifications: loadHistory,
  };
}
