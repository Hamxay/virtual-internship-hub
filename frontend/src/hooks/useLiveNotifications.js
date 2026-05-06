import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNotificationToast } from '../components/ui/NotificationToast';
import { getNotifications, markAsRead as markAsReadApi, markAllAsRead as markAllAsReadApi } from '../api/notifications.api';
import { API_BASE_URL } from '../api/client';

function buildNotificationsWsUrl(token) {
  const base = API_BASE_URL || 'http://localhost:8001/api';
  try {
    const u = new URL(base);
    const wsProto = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProto}//${u.host}/ws/notifications/?token=${encodeURIComponent(token)}`;
  } catch {
    return `ws://localhost:8001/ws/notifications/?token=${encodeURIComponent(token)}`;
  }
}

/**
 * FR10 live notifications + REST history (students & mentors).
 * @param {{ enabled: boolean }} opts
 */
export function useLiveNotifications({ enabled }) {
  const { addToast } = useNotificationToast();
  const { isAuthenticated } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const allowReconnectRef = useRef(true);

  const loadHistory = useCallback(async () => {
    try {
      const list = await getNotifications();
      setNotifications(Array.isArray(list) ? list : []);
      setUnreadCount((Array.isArray(list) ? list : []).filter((n) => !n.is_read).length);
    } catch {
      setNotifications([]);
      setUnreadCount(0);
    }
  }, []);

  useEffect(() => {
    if (!enabled || !isAuthenticated) {
      setNotifications([]);
      setUnreadCount(0);
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
            const data = JSON.parse(event.data);
            setNotifications((prev) => [data, ...prev.filter((n) => n.id !== data.id)]);
            setUnreadCount((c) => c + 1);
            addToast({ message: data.message || 'New notification' });
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
    try {
      await markAsReadApi(id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      /* ignore */
    }
  }, []);

  const markAllAsRead = useCallback(async () => {
    await markAllAsReadApi();
    setNotifications([]);
    setUnreadCount(0);
  }, []);

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
