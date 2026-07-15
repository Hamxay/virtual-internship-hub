import React, { useRef, useEffect, useMemo, useState } from 'react';
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
  if (text.toLowerCase().includes('plagiarism')) {
    return { label: 'Plagiarism scan', title: 'Plagiarism scan finished', detail: text };
  }
  if (text.toLowerCase().includes('chat message')) {
    return { label: 'Chat', title: 'New chat message', detail: text };
  }
  if (text.toLowerCase().includes('ai evaluation')) {
    return { label: 'AI feedback', title: 'Your project was evaluated', detail: text };
  }
  if (text.toLowerCase().includes('sent back') || text.toLowerCase().includes('revision')) {
    return { label: 'Needs Changes', title: 'Action required on your project', detail: text };
  }
  return { label: 'Update', title: 'Recent activity', detail: text };
}

function dashboardBasePath(user) {
  if (user?.role === 'MENTOR') return '/mentor/dashboard';
  if (user?.role === 'STUDENT') return '/student/dashboard';
  if (user?.role === 'ADMINISTRATOR') return '/admin/dashboard';
  return '/dashboard';
}

export default function Navbar({ variant = 'light' }) {
  const { user, isAuthenticated } = useAuth();
  const isStudent = user?.role === 'STUDENT';
  const navigate = useNavigate();
  const homePath = dashboardBasePath(user);
  const enabled =
    isAuthenticated && (user?.role === 'STUDENT' || user?.role === 'MENTOR');
  const {
    notifications,
    unreadCount,
    dropdownOpen,
    setDropdownOpen,
    markAsRead,
    markAllAsRead,
    refreshNotifications,
  } = useLiveNotifications({ enabled });

  const [showReadHistory, setShowReadHistory] = useState(false);
  const wrapRef = useRef(null);

  let reviewOnlyMode = false;
  try {
    reviewOnlyMode = Boolean(JSON.parse(localStorage.getItem(NOTIFICATION_PREFS_KEY) || '{}')?.reviewOnlyMode);
  } catch {
    reviewOnlyMode = false;
  }

  const effectiveReviewOnly = reviewOnlyMode && !isStudent;
  const visibleNotifications = useMemo(
    () =>
      effectiveReviewOnly
        ? notifications.filter((entry) => {
            const text = String(entry?.message || '').toLowerCase();
            return (
              text.includes('review')
              || text.includes('submitted')
              || text.includes('ai evaluation')
              || text.includes('plagiarism')
              || text.includes('chat message')
            );
          })
        : notifications,
    [effectiveReviewOnly, notifications],
  );
  const unreadInPanel = useMemo(
    () => visibleNotifications.filter((entry) => entry && entry.is_read !== true),
    [visibleNotifications],
  );
  const listToRender = showReadHistory ? visibleNotifications : unreadInPanel;
  const visibleUnreadCount = visibleNotifications.filter((entry) => entry && entry.is_read !== true).length;
  const badgeCount = effectiveReviewOnly ? visibleUnreadCount : unreadCount;
  const badgeLabel = badgeCount > 9 ? '9+' : String(badgeCount);

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

  useEffect(() => {
    if (!dropdownOpen) setShowReadHistory(false);
  }, [dropdownOpen]);

  if (!enabled) return null;

  const handleItemClick = async (notification) => {
    const text = String(notification?.message || '').toLowerCase();
    const mentorWantsReview =
      user?.role === 'MENTOR'
      && (
        (text.includes('submitted') && text.includes('review'))
        || text.includes('pending mentor review')
        || text.includes('mentor review')
        || text.includes('needs mentor')
        || text.includes('needs review')
      );
    if (notification.is_read !== true) {
      try {
        await markAsRead(notification.id);
      } catch {
        /* still navigate */
      }
    }
    setDropdownOpen(false);
    if (mentorWantsReview) {
      const notifHint = encodeURIComponent(String(notification?.message || ''));
      navigate(`${homePath}?mentor_tab=reviews&notif_hint=${notifHint}`);
      return;
    }
    const path = notification.link && notification.link.startsWith('/') ? notification.link : homePath;
    navigate(path);
  };

  return (
    <div className="relative inline-flex items-center" ref={wrapRef}>
      <button
        type="button"
        className={`relative inline-flex h-10 w-10 items-center justify-center rounded-lg border transition ${
          variant === 'dark'
            ? dropdownOpen
              ? 'border-teal-400 bg-white/10 text-teal-100'
              : 'border-slate-500 bg-slate-800/80 text-slate-100 hover:bg-slate-700 hover:text-white'
            : dropdownOpen
              ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
              : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900'
        }`}
        aria-label="Notifications"
        aria-expanded={dropdownOpen}
        onClick={() => setDropdownOpen((o) => !o)}
      >
        <BellIcon className="h-5 w-5" />
        {badgeCount > 0 ? (
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
              {badgeCount > 0 ? (
                <span className="inline-flex min-w-[22px] items-center justify-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                  {badgeCount}
                </span>
              ) : null}
            </div>
            <button
              type="button"
              disabled={badgeCount === 0}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 disabled:cursor-not-allowed disabled:opacity-40"
              onClick={async () => {
                try {
                  await markAllAsRead();
                  setShowReadHistory(false);
                } catch {
                  try {
                    await refreshNotifications();
                  } catch {
                    /* ignore */
                  }
                }
              }}
            >
              Mark all as read
            </button>
          </div>

          <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-500">
            {showReadHistory
              ? 'Including read items from your recent history.'
              : effectiveReviewOnly
                ? 'New items only (review and chat). Change filter in Profile settings.'
                : 'New items only — use “Show read” below for history.'}
          </div>

          <div className="max-h-[360px] overflow-y-auto">
            <div className="px-2 py-2">
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
            ) : listToRender.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 px-4 py-10 text-center">
                <p className="text-sm font-medium text-slate-700">You&apos;re all caught up.</p>
                <p className="text-xs text-slate-500">Nothing unread in this list. Mark all as read cleared new alerts.</p>
                {visibleNotifications.some((entry) => entry?.is_read === true) ? (
                  <button
                    type="button"
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                    onClick={() => setShowReadHistory(true)}
                  >
                    Show read notifications
                  </button>
                ) : null}
              </div>
            ) : (
              listToRender.map((notification) => {
                const meta = getNotificationMeta(notification.message);
                return (
                <button
                  key={notification.id}
                  type="button"
                  onClick={() => handleItemClick(notification)}
                  className={`mb-2 w-full rounded-xl border px-3 py-3 text-left transition ${
                    notification.is_read !== true
                      ? 'border-indigo-200 bg-indigo-50/60'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <span className="mb-1 inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-700">
                    {meta.label}
                  </span>
                  <span className="block text-sm font-semibold text-slate-900">{meta.title}</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-slate-600">{meta.detail}</span>
                  {notification.created_at ? (
                    <span className="mt-1 block text-[11px] text-slate-400">
                      {formatRelativeTime(notification.created_at)}
                    </span>
                  ) : null}
                </button>
                );
              })
            )}
            {!showReadHistory && unreadInPanel.length > 0 && visibleNotifications.length > unreadInPanel.length ? (
              <button
                type="button"
                className="mb-2 w-full py-2 text-center text-xs font-semibold text-slate-500 hover:text-slate-800"
                onClick={() => setShowReadHistory(true)}
              >
                Show read ({visibleNotifications.length - unreadInPanel.length})
              </button>
            ) : null}
            {showReadHistory ? (
              <button
                type="button"
                className="mb-2 w-full py-2 text-center text-xs font-semibold text-slate-500 hover:text-slate-800"
                onClick={() => setShowReadHistory(false)}
              >
                Hide read — new only
              </button>
            ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
