import React, { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useLiveNotifications } from '../../hooks/useLiveNotifications';
import { BellIcon } from '../ui/Icons';

function formatRelativeTime(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

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

  const badgeLabel = unreadCount > 9 ? '9+' : String(unreadCount);

  return (
    <div className="notif-bell-wrap" ref={wrapRef}>
      <button
        type="button"
        className="notif-bell-btn"
        aria-label="Notifications"
        aria-expanded={dropdownOpen}
        onClick={() => setDropdownOpen((o) => !o)}
      >
        <BellIcon className="notif-bell-icon" />
        {unreadCount > 0 ? (
          <span className="notif-badge" aria-hidden>
            {badgeLabel}
          </span>
        ) : null}
      </button>

      {dropdownOpen ? (
        <div className="notif-dropdown">
          <div className="notif-dropdown__header">
            <div className="notif-dropdown__title-row">
              <span className="notif-dropdown__title">Notifications</span>
              {unreadCount > 0 ? (
                <span className="notif-dropdown__count-chip">{unreadCount}</span>
              ) : null}
            </div>
            <button
              type="button"
              className="notif-dropdown__mark-all"
              onClick={async () => {
                try {
                  await markAllAsRead();
                } catch {
                  /* ignore */
                }
              }}
            >
              Mark all read
            </button>
          </div>

          <div className="notif-dropdown__list">
            {notifications.length === 0 ? (
              <div className="notif-empty">
                <svg
                  className="notif-empty__icon"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                  />
                </svg>
                <p className="notif-empty__msg">No notifications yet.</p>
              </div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleItemClick(n)}
                  className={`notif-item${!n.is_read ? ' notif-item--unread' : ''}`}
                >
                  <span className="notif-item__msg">{n.message}</span>
                  {n.created_at ? (
                    <span className="notif-item__time">
                      {formatRelativeTime(n.created_at)}
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
