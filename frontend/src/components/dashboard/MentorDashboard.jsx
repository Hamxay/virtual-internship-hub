import React, { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { mentorApi } from '../../api/mentor.api';
import { getDomains } from '../../api/domains.api';
import { buildMentorProfilePayload } from '../../services/mentor.service';
import Navbar from '../layout/Navbar';
import MentorTriageDashboard from '../mentor/MentorTriageDashboard';
import ReviewQueue from '../mentor/ReviewQueue';
import MentorStudentChatTab from '../chat/MentorStudentChatTab';

const TAB = {
  STUDENTS: 'students',
  REVIEWS: 'reviews',
  CHAT: 'chat',
  PROFILE: 'profile',
};
const NOTIFICATION_PREFS_KEY = 'mentor_notification_preferences_v1';

function initialMentorTabFromUrl() {
  if (typeof window === 'undefined') return TAB.STUDENTS;
  try {
    const p = new URLSearchParams(window.location.search);
    if (p.get('mentor_tab') === 'reviews') return TAB.REVIEWS;
    if (p.get('mentor_tab') === 'chat') return TAB.CHAT;
    return TAB.STUDENTS;
  } catch {
    return TAB.STUDENTS;
  }
}

function loadNotificationPrefs() {
  try {
    const raw = localStorage.getItem(NOTIFICATION_PREFS_KEY);
    if (!raw) {
      return {
        browserAlerts: true,
        soundAlerts: false,
        reviewOnlyMode: true,
      };
    }
    const parsed = JSON.parse(raw);
    return {
      browserAlerts: Boolean(parsed?.browserAlerts),
      soundAlerts: Boolean(parsed?.soundAlerts),
      reviewOnlyMode: Boolean(parsed?.reviewOnlyMode),
    };
  } catch {
    return {
      browserAlerts: true,
      soundAlerts: false,
      reviewOnlyMode: true,
    };
  }
}

function MentorDashboard() {
  const location = useLocation();
  const { user, logout, refreshUser } = useAuth();
  const [tab, setTab] = useState(initialMentorTabFromUrl);
  const [students, setStudents] = useState([]);
  const [studentsLoading, setStudentsLoading] = useState(true);
  const [domains, setDomains] = useState([]);
  const [profileForm, setProfileForm] = useState({
    professional_bio: '',
    expertise_domain_id: '',
    years_of_experience: 0,
    is_available: true,
  });
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState('');
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [notificationPrefs, setNotificationPrefs] = useState(loadNotificationPrefs);

  const mentorName = user?.username || 'Mentor';
  const profile = user?.mentor_profile;
  const domainName = profile?.expertise_domain?.name;
  const studentsNeedingHelp = students.filter((s) => s?.skill_insights?.trend_direction === 'DOWN').length;
  const studentsImproving = students.filter((s) => s?.skill_insights?.trend_direction === 'UP').length;
  const avgScore = students.length
    ? (students.reduce((sum, s) => sum + (Number(s?.domain_average) || 0), 0) / students.length).toFixed(1)
    : '0.0';

  useEffect(() => {
    localStorage.setItem(NOTIFICATION_PREFS_KEY, JSON.stringify(notificationPrefs));
  }, [notificationPrefs]);

  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const notificationHint = searchParams.get('notif_hint') || '';

  useEffect(() => {
    const m = searchParams.get('mentor_tab');
    if (m === 'reviews') setTab(TAB.REVIEWS);
    else if (m === 'chat') setTab(TAB.CHAT);
    else if (m === 'students') setTab(TAB.STUDENTS);
  }, [searchParams]);

  const loadStudents = () => {
    setStudentsLoading(true);
    mentorApi
      .getStudents()
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
        setStudents(list);
      })
      .catch(() => setStudents([]))
      .finally(() => setStudentsLoading(false));
  };

  useEffect(() => {
    loadStudents();
  }, []);

  useEffect(() => {
    if (tab === TAB.PROFILE) {
      getDomains().then((list) => setDomains(Array.isArray(list) ? list : []));
      setProfileForm({
        professional_bio: profile?.professional_bio ?? '',
        expertise_domain_id: profile?.expertise_domain?.id ?? '',
        years_of_experience: profile?.years_of_experience ?? 0,
        is_available: profile?.is_available ?? true,
      });
      setProfileError('');
      setProfileSuccess(false);
    }
  }, [tab, profile?.professional_bio, profile?.expertise_domain?.id, profile?.years_of_experience, profile?.is_available]);

  const handleLogout = async () => {
    await logout();
    window.location.href = '/';
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setProfileError('');
    setProfileSuccess(false);
    setProfileSaving(true);
    try {
      await mentorApi.updateProfile(buildMentorProfilePayload(profileForm));
      if (typeof refreshUser === 'function') await refreshUser();
      setProfileSuccess(true);
      loadStudents();
    } catch (err) {
      setProfileError(
        err.response?.data?.detail || err.response?.data?.professional_bio?.[0] || 'Failed to save profile.',
      );
    } finally {
      setProfileSaving(false);
    }
  };

  const tabBtn = (id, label) => (
    <button
      key={id}
      type="button"
      onClick={() => setTab(id)}
      className={`relative rounded-lg px-4 py-2.5 text-sm font-semibold transition sm:text-base ${
        tab === id
          ? 'bg-violet-100 text-violet-900 shadow-sm ring-1 ring-violet-200'
          : 'text-slate-600 hover:bg-white hover:text-slate-900'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-40 border-b border-violet-200 bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-gradient-to-r supports-[backdrop-filter]:from-violet-500 supports-[backdrop-filter]:via-purple-500 supports-[backdrop-filter]:to-fuchsia-500">
        <div className="h-1 w-full bg-gradient-to-r from-fuchsia-300 via-violet-200 to-purple-300" aria-hidden />
        <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-10">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-violet-100">Mentor workspace</p>
            <h1 className="mt-1 text-lg font-semibold tracking-tight text-white sm:text-xl">
              Virtual Internship Hub
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-violet-100 sm:text-base">
              <span className="font-medium text-white">{mentorName}</span>
              {domainName ? (
                <>
                  <span className="text-violet-200">·</span>
                  <span className="rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-semibold text-white ring-1 ring-white/30 sm:text-sm">
                    {domainName}
                  </span>
                </>
              ) : (
                <span className="text-amber-100">Add your focus domain in Profile</span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Navbar />
            <nav className="inline-flex rounded-xl bg-white/20 p-1 ring-1 ring-white/30">
              {tabBtn(TAB.STUDENTS, 'Students')}
              {tabBtn(TAB.REVIEWS, 'Review work')}
              {tabBtn(TAB.CHAT, 'Chats')}
            </nav>
            <button
              type="button"
              onClick={() => setTab(TAB.PROFILE)}
              className={`rounded-lg px-4 py-2.5 text-sm font-semibold sm:text-base ${
                tab === TAB.PROFILE
                  ? 'bg-violet-100 text-violet-900 shadow-sm hover:bg-violet-50'
                  : 'border border-white/40 bg-white/15 text-white shadow-sm hover:bg-white/25'
              }`}
            >
              Profile
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg border border-white/40 bg-white/15 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-white/25 sm:text-base"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-6 lg:px-10">
        {tab === TAB.STUDENTS && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-cyan-100 bg-white/90 px-5 py-5 shadow-md shadow-cyan-100/40">
              <h2 className="text-xl font-semibold text-slate-900">Students at a glance</h2>
              <p className="mt-1 text-sm text-slate-600">Focus on who needs support now and who is moving forward.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-xl border border-cyan-100 bg-cyan-50/70 px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Students</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-900">{students.length}</p>
                </div>
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-red-700">Need support now</p>
                  <p className="mt-1 text-2xl font-semibold text-red-800">{studentsNeedingHelp}</p>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">Improving</p>
                  <p className="mt-1 text-2xl font-semibold text-emerald-800">{studentsImproving}</p>
                </div>
                <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-indigo-700">Average result</p>
                  <p className="mt-1 text-2xl font-semibold text-indigo-800">{avgScore}</p>
                </div>
              </div>
            </div>
            <MentorTriageDashboard students={students} loading={studentsLoading} />
          </div>
        )}

        {tab === TAB.REVIEWS && <ReviewQueue notificationHint={notificationHint} />}
        {tab === TAB.CHAT && <MentorStudentChatTab role="mentor" />}

        {tab === TAB.PROFILE && (
          <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
            <div className="rounded-2xl border border-cyan-100 bg-white/90 p-6 shadow-md shadow-cyan-100/40">
              <h2 className="text-lg font-semibold text-slate-900">Profile details</h2>
              <p className="mt-1 text-sm text-slate-600">Update your mentor details and teaching availability.</p>
              {profileError ? (
                <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{profileError}</p>
              ) : null}
              {profileSuccess ? (
                <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Profile saved.</p>
              ) : null}
              <form onSubmit={handleSaveProfile} className="mt-6 space-y-4">
                <label className="block text-sm font-medium text-slate-700">
                  About you
                  <textarea
                    value={profileForm.professional_bio}
                    onChange={(e) => setProfileForm((f) => ({ ...f, professional_bio: e.target.value }))}
                    rows={4}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="Share your background and mentoring style"
                  />
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Focus domain
                  <select
                    value={profileForm.expertise_domain_id}
                    onChange={(e) => setProfileForm((f) => ({ ...f, expertise_domain_id: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="">Choose a domain</option>
                    {domains.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm font-medium text-slate-700">
                  Years mentoring
                  <input
                    type="number"
                    min={0}
                    value={profileForm.years_of_experience}
                    onChange={(e) => setProfileForm((f) => ({ ...f, years_of_experience: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </label>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={profileForm.is_available}
                    onChange={(e) => setProfileForm((f) => ({ ...f, is_available: e.target.checked }))}
                    className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  Available for students
                </label>
                <button
                  type="submit"
                  disabled={profileSaving}
                  className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow hover:bg-indigo-700 disabled:opacity-60"
                >
                  {profileSaving ? 'Saving…' : 'Save changes'}
                </button>
              </form>
            </div>

            <div className="rounded-2xl border border-cyan-100 bg-white/90 p-6 shadow-md shadow-cyan-100/40">
              <h3 className="text-lg font-semibold text-slate-900">Notification settings</h3>
              <p className="mt-1 text-sm text-slate-600">Choose how you want to get updates while mentoring.</p>
              <div className="mt-5 space-y-3">
                <label className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 p-3">
                  <div>
                    <p className="text-sm font-medium text-slate-900">In-app popups</p>
                    <p className="text-xs text-slate-500">Show popup alerts inside dashboard</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={notificationPrefs.browserAlerts}
                    onChange={(e) => setNotificationPrefs((p) => ({ ...p, browserAlerts: e.target.checked }))}
                    className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </label>
                <label className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 p-3">
                  <div>
                    <p className="text-sm font-medium text-slate-900">Sound alert</p>
                    <p className="text-xs text-slate-500">Play a sound when new work arrives</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={notificationPrefs.soundAlerts}
                    onChange={(e) => setNotificationPrefs((p) => ({ ...p, soundAlerts: e.target.checked }))}
                    className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </label>
                <label className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 p-3">
                  <div>
                    <p className="text-sm font-medium text-slate-900">Review-focused feed</p>
                    <p className="text-xs text-slate-500">Keep only review related items at top</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={notificationPrefs.reviewOnlyMode}
                    onChange={(e) => setNotificationPrefs((p) => ({ ...p, reviewOnlyMode: e.target.checked }))}
                    className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </label>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default MentorDashboard;
