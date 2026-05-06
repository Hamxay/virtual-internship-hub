import React, { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useLiveNotifications } from '../../hooks/useLiveNotifications';
import { BellIcon } from '../ui/Icons';

const NOTIFICATION_PREFS_KEY = 'mentor_notification_preferences_v1';

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

function getNotificationMeta(message = '') {
  const text = String(message || '').trim();
  if (!text) {
    return { label: 'Update', title: 'New update', detail: '' };
  }
  if (text.toLowerCase().includes('submitted') && text.toLowerCase().includes('review')) {
    return { label: 'New Submission', title: 'Student work needs feedback', detail: text };
  }
  if (text.toLowerCase().includes('mentor') && text.toLowerCase().includes('approved')) {
    return { label: 'Reviewed', title: 'Your project was reviewed', detail: text };
  }
  if (text.toLowerCase().includes('sent back') || text.toLowerCase().includes('revision')) {
    return { label: 'Needs Changes', title: 'Action required on your project', detail: text };
  }
  return { label: 'Update', title: 'Recent activity', detail: text };
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

  let reviewOnlyMode = false;
  try {
    reviewOnlyMode = Boolean(JSON.parse(localStorage.getItem(NOTIFICATION_PREFS_KEY) || '{}')?.reviewOnlyMode);
  } catch {
    reviewOnlyMode = false;
  }

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
    const isReviewRelated = String(n?.message || '').toLowerCase().includes('review');
    if (!n.is_read) {
      try {
        await markAsRead(n.id);
      } catch {
        /* still navigate */
      }
    }
    setDropdownOpen(false);
    if (isReviewRelated) {
      const notifHint = encodeURIComponent(String(n?.message || ''));
      navigate(`/dashboard?mentor_tab=reviews&notif_hint=${notifHint}`);
      return;
    }
    const path = n.link && n.link.startsWith('/') ? n.link : '/dashboard';
    navigate(path);
  };

  const badgeLabel = unreadCount > 9 ? '9+' : String(unreadCount);
  const visibleNotifications = reviewOnlyMode
    ? notifications.filter((n) => {
        const text = String(n?.message || '').toLowerCase();
        return text.includes('review') || text.includes('submitted');
      })
    : notifications;

  return (
    <div className="relative inline-flex items-center" ref={wrapRef}>
      <button
        type="button"
        className={`relative inline-flex h-10 w-10 items-center justify-center rounded-lg border transition ${
          dropdownOpen
            ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900'
        }`}
        aria-label="Notifications"
        aria-expanded={dropdownOpen}
        onClick={() => setDropdownOpen((o) => !o)}
      >
        <BellIcon className="h-5 w-5" />
        {unreadCount > 0 ? (
          <span className="absolute -right-1 -top-1 inline-flex min-w-[18px] items-center justify-center rounded-full bg-red-500 px-1.5 py-0.5 text-[11px] font-bold text-white shadow-sm" aria-hidden>
            {badgeLabel}
          </span>
        ) : null}
      </button>

      {dropdownOpen ? (
        <div className="absolute right-0 top-[calc(100%+10px)] z-[200] w-[420px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">Notifications</span>
              {unreadCount > 0 ? (
                <span className="inline-flex min-w-[22px] items-center justify-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                  {unreadCount}
                </span>
              ) : null}
            </div>
            <button
              type="button"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
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

          <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-500">
            {reviewOnlyMode
              ? 'Showing review-focused updates. You can change this in Profile settings.'
              : 'Showing all recent updates and review activity.'}
          </div>

          <div className="max-h-[360px] overflow-y-auto">
            <div className="px-2 py-2">
              {reviewOnlyMode
                ? null
                : null}
            {visibleNotifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 px-4 py-12 text-center">
                <svg
                  className="h-9 w-9 text-slate-300"
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
                <p className="text-sm text-slate-500">No notifications yet.</p>
              </div>
            ) : (
              visibleNotifications.map((n) => {
                const meta = getNotificationMeta(n.message);
                return (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleItemClick(n)}
                  className={`mb-2 w-full rounded-xl border px-3 py-3 text-left transition ${
                    !n.is_read
                      ? 'border-indigo-200 bg-indigo-50/60'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <span className="mb-1 inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-700">
                    {meta.label}
                  </span>
                  <span className="block text-sm font-semibold text-slate-900">{meta.title}</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-slate-600">{meta.detail}</span>
                  {n.created_at ? (
                    <span className="mt-1 block text-[11px] text-slate-400">
                      {formatRelativeTime(n.created_at)}
                    </span>
                  ) : null}
                </button>
                );
              })
            )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
