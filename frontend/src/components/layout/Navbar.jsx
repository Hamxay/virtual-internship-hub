import React, { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useLiveNotifications } from '../../hooks/useLiveNotifications';
import { BellIcon } from '../ui/Icons';

/**
 * Bell + dropdown for FR10 notifications. Mount inside authenticated dashboards only.
 * Does not replace full nav chrome — only injects this block.
 */
export default function Navbar() {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const enabled =
    isAuthenticated && (user?.role === 'STUDENT' || user?.role === 'MENTOR');
  const {
    notifications,
    unreadCount,
    dropdownOpen,
    setDropdownOpen,
    markAsRead,
    markAllAsRead,
  } = useLiveNotifications({ enabled });

  const wrapRef = useRef(null);

  useEffect(() => {
    if (!dropdownOpen) return undefined;
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [dropdownOpen, setDropdownOpen]);

  if (!enabled) return null;

  const handleItemClick = async (n) => {
    if (!n.is_read) {
      try {
        await markAsRead(n.id);
      } catch {
        /* still navigate */
      }
    }
    setDropdownOpen(false);
    const path = n.link && n.link.startsWith('/') ? n.link : '/dashboard';
    navigate(path);
  };

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        className="relative rounded p-2 text-gray-600 hover:bg-gray-100"
        aria-label="Notifications"
        aria-expanded={dropdownOpen}
        onClick={() => setDropdownOpen((o) => !o)}
      >
        <BellIcon className="h-5 w-5" />
        {unreadCount > 0 ? (
          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500" aria-hidden />
        ) : null}
      </button>

      {dropdownOpen ? (
        <div className="absolute right-0 z-50 mt-1 w-80 rounded border border-gray-200 bg-white text-left text-sm text-gray-900 shadow-md">
          <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2">
            <span className="font-medium text-gray-900">Notifications</span>
            <button
              type="button"
              className="text-xs text-gray-600 underline hover:text-gray-900"
              onClick={async () => {
                try {
                  await markAllAsRead();
                } catch {
                  /* ignore */
                }
              }}
            >
              Mark all as read
            </button>
          </div>
          <div className="max-h-72 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-3 py-4 text-gray-500">No notifications yet.</p>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleItemClick(n)}
                  className={`block w-full border-b border-gray-50 px-3 py-2 text-left last:border-0 hover:bg-gray-50 ${
                    !n.is_read ? 'bg-gray-50/80' : ''
                  }`}
                >
                  <span className="text-gray-900">{n.message}</span>
                  {n.created_at ? (
                    <span className="mt-0.5 block text-xs text-gray-400">
                      {new Date(n.created_at).toLocaleString()}
                    </span>
                  ) : null}
                </button>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
