import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { mentorApi } from '../../api/mentor.api';
import { getDomains } from '../../api/domains.api';
import { buildMentorProfilePayload } from '../../services/mentor.service';
import MentorReviewQueue from './MentorReviewQueue';
import Navbar from '../layout/Navbar';
import './Dashboard.css';

const VIEW = { HOME: 'home', REVIEWS: 'reviews', PROFILE: 'profile' };

function MentorDashboard() {
  const { user, logout, refreshUser } = useAuth();
  const [view, setView] = useState(VIEW.HOME);
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

  const mentorName = user?.username || user?.mentor_profile?.user?.username || 'Mentor';
  const profile = user?.mentor_profile;

  const loadStudents = () => {
    setStudentsLoading(true);
    mentorApi.getStudents()
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setStudents(list);
      })
      .catch(() => setStudents([]))
      .finally(() => setStudentsLoading(false));
  };

  useEffect(() => {
    loadStudents();
  }, []);

  useEffect(() => {
    if (view === VIEW.PROFILE) {
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
  }, [view, profile?.professional_bio, profile?.expertise_domain?.id, profile?.years_of_experience, profile?.is_available]);

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
    } catch (err) {
      setProfileError(err.response?.data?.detail || err.response?.data?.professional_bio?.[0] || 'Failed to save profile.');
    } finally {
      setProfileSaving(false);
    }
  };

  return (
    <div className="dashboard-container mentor-dashboard">
      <nav className="dashboard-nav mentor-dashboard-nav">
        <div className="mentor-dashboard-nav-inner">
          <div className="mentor-nav-left">
            <div className="mentor-logo">
              <span className="mentor-logo-icon">M</span>
              <div>
                <div className="mentor-logo-title">Virtual Internship Hub</div>
                <div className="mentor-logo-sub">Mentor Portal</div>
              </div>
            </div>
            <button
              type="button"
              className={`mentor-nav-btn ${view === VIEW.HOME ? 'active' : ''}`}
              onClick={() => setView(VIEW.HOME)}
            >
              Students
            </button>
            <button
              type="button"
              className={`mentor-nav-btn ${view === VIEW.REVIEWS ? 'active' : ''}`}
              onClick={() => setView(VIEW.REVIEWS)}
            >
              Review queue
            </button>
          </div>
          <div className="mentor-nav-right flex items-center gap-2">
            <Navbar />
            <div className="mentor-user-meta">
              <span className="mentor-user-name">{mentorName}</span>
              <span className="mentor-user-role">Mentor</span>
            </div>
            <button
              type="button"
              className="mentor-nav-icon-btn"
              onClick={() => setView(VIEW.PROFILE)}
              title="My profile"
              aria-label="Profile"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
            </button>
            <button type="button" className="mentor-nav-icon-btn" onClick={handleLogout} title="Logout" aria-label="Logout">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
            </button>
          </div>
        </div>
      </nav>

      <div className="mentor-dashboard-content">
        {view === VIEW.REVIEWS && (
          <MentorReviewQueue />
        )}

        {view === VIEW.HOME && (
          <>
            <div className="mentor-welcome-card">
              <h2>Welcome, {mentorName}</h2>
              <p>
                {profile?.expertise_domain?.name
                  ? `Students below are in your expertise domain: ${profile.expertise_domain.name}. Use the profile icon above to update your own profile.`
                  : 'Set your expertise domain in Profile (profile icon above) to see students in your domain.'}
              </p>
            </div>

            <section className="mentor-section-card">
              <h3>{profile?.expertise_domain?.name ? `Students in ${profile.expertise_domain.name}` : 'Students'}</h3>
              <p className="mentor-section-desc">
                {profile?.expertise_domain?.name
                  ? 'Students whose target domains include your expertise domain.'
                  : 'Set your expertise domain in Profile to see only students in your domain.'}
              </p>
              {studentsLoading ? (
                <p className="mentor-loading">Loading students…</p>
              ) : students.length === 0 ? (
                <p className="mentor-empty">No students yet.</p>
              ) : (
                <ul className="mentor-student-list">
                  {students.map((s, idx) => (
                    <li key={`${s.first_name}-${s.last_name}-${idx}`} className="mentor-student-card">
                      <div className="mentor-student-name">
                        {s.first_name} {s.last_name}
                      </div>
                      <div className="mentor-student-domains">
                        <span className="mentor-student-domains-label">Domain expertise:</span>
                        {(s.target_domains || []).length > 0 ? (
                          (s.target_domains || []).map((d) => (
                            <span key={d.id} className="mentor-domain-tag">{d.name}</span>
                          ))
                        ) : (
                          <span className="mentor-domain-none">Not set</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}

        {view === VIEW.PROFILE && (
          <section className="mentor-section-card mentor-profile-card">
            <h3>My Profile</h3>
            <p className="mentor-section-desc">Update your professional bio, expertise domain, and availability.</p>
            {profileError && <p className="mentor-profile-error">{profileError}</p>}
            {profileSuccess && <p className="mentor-profile-success">Profile saved successfully.</p>}
            <form onSubmit={handleSaveProfile} className="mentor-profile-form">
              <label className="mentor-form-label">
                Professional bio
                <textarea
                  value={profileForm.professional_bio}
                  onChange={(e) => setProfileForm((f) => ({ ...f, professional_bio: e.target.value }))}
                  className="mentor-form-input mentor-form-textarea"
                  rows={4}
                  placeholder="Your background and how you mentor"
                />
              </label>
              <label className="mentor-form-label">
                Expertise domain
                <select
                  value={profileForm.expertise_domain_id}
                  onChange={(e) => setProfileForm((f) => ({ ...f, expertise_domain_id: e.target.value }))}
                  className="mentor-form-input mentor-form-select"
                >
                  <option value="">Select domain</option>
                  {domains.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </label>
              <label className="mentor-form-label">
                Years of experience
                <input
                  type="number"
                  min={0}
                  value={profileForm.years_of_experience}
                  onChange={(e) => setProfileForm((f) => ({ ...f, years_of_experience: e.target.value }))}
                  className="mentor-form-input"
                />
              </label>
              <label className="mentor-form-label mentor-form-check">
                <input
                  type="checkbox"
                  checked={profileForm.is_available}
                  onChange={(e) => setProfileForm((f) => ({ ...f, is_available: e.target.checked }))}
                />
                <span>Available for mentoring</span>
              </label>
              <button type="submit" className="mentor-btn-save" disabled={profileSaving}>
                {profileSaving ? 'Saving…' : 'Save profile'}
              </button>
            </form>
            <button type="button" className="mentor-btn-back" onClick={() => { loadStudents(); setView(VIEW.HOME); }}>
              ← Back to Students
            </button>
          </section>
        )}
      </div>
    </div>
  );
}

export default MentorDashboard;
