import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { mentorApi } from '../../api/mentor.api';
import { getDomains } from '../../api/domains.api';
import { buildMentorProfilePayload } from '../../services/mentor.service';
import Navbar from '../layout/Navbar';
import StudentProgressTable from '../mentor/StudentProgressTable';
import ReviewQueue from '../mentor/ReviewQueue';

const TAB = { STUDENTS: 'students', REVIEWS: 'reviews', PROFILE: 'profile' };

function MentorDashboard() {
  const { user, logout, refreshUser } = useAuth();
  const [tab, setTab] = useState(TAB.STUDENTS);
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

  const mentorName = user?.username || 'Mentor';
  const profile = user?.mentor_profile;
  const domainName = profile?.expertise_domain?.name;

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
      className={`relative rounded-lg px-4 py-2 text-sm font-semibold transition ${
        tab === id
          ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-indigo-600">Mentor portal</p>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900">Virtual Internship Hub</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <span className="font-medium text-slate-800">{mentorName}</span>
              {domainName ? (
                <>
                  <span className="text-slate-400">·</span>
                  <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-800 ring-1 ring-indigo-100">
                    {domainName}
                  </span>
                </>
              ) : (
                <span className="text-amber-700">Set your expertise domain in My profile</span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Navbar />
            <nav className="inline-flex rounded-lg bg-slate-100/90 p-1 ring-1 ring-slate-200/80">
              {tabBtn(TAB.STUDENTS, 'My students')}
              {tabBtn(TAB.REVIEWS, 'Needs review')}
            </nav>
            <button
              type="button"
              onClick={() => setTab(TAB.PROFILE)}
              className={`rounded-lg px-3 py-2 text-sm font-semibold ${
                tab === TAB.PROFILE ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              My profile
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {tab === TAB.STUDENTS && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-slate-900">Student progress</h2>
              <p className="mt-1 max-w-2xl text-sm text-slate-600">
                Coaching view scoped to your expertise domain: completion counts, average evaluated score, and at-risk
                signals.
              </p>
            </div>
            <StudentProgressTable students={students} loading={studentsLoading} />
          </div>
        )}

        {tab === TAB.REVIEWS && <ReviewQueue />}

        {tab === TAB.PROFILE && (
          <div className="mx-auto max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">My profile</h2>
            <p className="mt-1 text-sm text-slate-600">Bio, expertise domain, and availability.</p>
            {profileError ? (
              <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{profileError}</p>
            ) : null}
            {profileSuccess ? (
              <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Profile saved.</p>
            ) : null}
            <form onSubmit={handleSaveProfile} className="mt-6 space-y-4">
              <label className="block text-sm font-medium text-slate-700">
                Professional bio
                <textarea
                  value={profileForm.professional_bio}
                  onChange={(e) => setProfileForm((f) => ({ ...f, professional_bio: e.target.value }))}
                  rows={4}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="Your background and how you mentor"
                />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Expertise domain
                <select
                  value={profileForm.expertise_domain_id}
                  onChange={(e) => setProfileForm((f) => ({ ...f, expertise_domain_id: e.target.value }))}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="">Select domain</option>
                  {domains.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Years of experience
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
                Available for mentoring
              </label>
              <button
                type="submit"
                disabled={profileSaving}
                className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow hover:bg-indigo-700 disabled:opacity-60"
              >
                {profileSaving ? 'Saving…' : 'Save profile'}
              </button>
            </form>
            <button
              type="button"
              onClick={() => setTab(TAB.STUDENTS)}
              className="mt-4 text-sm font-medium text-indigo-600 hover:text-indigo-800"
            >
              ← Back to students
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default MentorDashboard;
