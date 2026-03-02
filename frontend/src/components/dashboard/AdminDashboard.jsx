/**
 * Admin Dashboard – FR8 (user/project/report management), FR10 (project templates & evaluation criteria).
 * Sections: Dashboard overview, Users (students/mentors only), Skill Assessments, Project Templates, Reports.
 */
import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { adminApi } from '../../api/admin.api';
import { useDomains, invalidateDomainsCache } from '../../hooks/useDomains';
import { buildDomainPayload, buildQuestionPayload } from '../../services/admin.service';
import {
  GraduationCapIcon,
  LayoutDashboardIcon,
  UsersIcon,
  FileTextIcon,
  FolderKanbanIcon,
  FolderOpenIcon,
  BarChartIcon,
  MenuIcon,
  XIcon,
  LogOutIcon,
  ClockIcon,
  PencilIcon,
  TrashIcon,
} from '../ui/Icons';
import './Dashboard.css';

const BASE_NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboardIcon, superadminOnly: false },
  { id: 'users', label: 'Users', icon: UsersIcon, superadminOnly: false },
  { id: 'assessments', label: 'Domain Questions', icon: FileTextIcon, superadminOnly: false },
  { id: 'domains', label: 'Domains', icon: FolderOpenIcon, superadminOnly: false },
  { id: 'projects', label: 'Project Templates', icon: FolderKanbanIcon, superadminOnly: false },
  { id: 'reports', label: 'Reports & Analytics', icon: BarChartIcon, superadminOnly: false },
];

function AdminDashboard() {
  const { user, logout } = useAuth();
  const isSuperadmin = Boolean(user?.is_superuser ?? user?.is_superadmin);
  const navItems = BASE_NAV_ITEMS.filter((item) => !item.superadminOnly || isSuperadmin);
  const [activeView, setActiveView] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    window.location.href = '/';
  };

  const renderContent = () => {
    switch (activeView) {
      case 'dashboard':
        return <AdminDashboardHome />;
      case 'users':
        return <AdminUsersSection />;
      case 'assessments':
        return <AdminAssessmentsSection />;
      case 'domains':
        return <AdminDomainsSection onDomainsChanged={invalidateDomainsCache} />;
      case 'projects':
        return <AdminProjectsPlaceholder />;
      case 'reports':
        return <AdminReportsPlaceholder />;
      default:
        return <AdminDashboardHome />;
    }
  };

  return (
    <div className={`dashboard-with-sidebar ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      {/* Top Navbar */}
      <nav className="dashboard-nav-top">
        <div className="nav-brand">
          <button
            type="button"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-2 hover:bg-gray-100 rounded-lg hidden lg:block"
            aria-label="Toggle sidebar"
          >
            <MenuIcon className="w-5 h-5 text-gray-600" />
          </button>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 hover:bg-gray-100 rounded-lg lg:hidden"
            aria-label="Menu"
          >
            {mobileMenuOpen ? <XIcon className="w-5 h-5" /> : <MenuIcon className="w-5 h-5" />}
          </button>
          <div className="flex items-center gap-3">
            <div className="logo-box">
              <GraduationCapIcon className="w-6 h-6" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-lg font-medium text-gray-900">Virtual Internship Hub</h1>
              <p className="text-xs text-gray-500">Admin Dashboard</p>
            </div>
          </div>
        </div>

        <div className="nav-user">
          <div className="user-box hidden md:block">
            <div className="user-name">{user?.username || 'Admin'}</div>
            <div className="user-role">{isSuperadmin ? 'Superadmin' : 'Admin'} · {user?.email || 'admin@example.com'}</div>
          </div>
          <button type="button" onClick={handleLogout} className="btn-logout-nav">
            <LogOutIcon className="w-4 h-4" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </nav>

      {/* Sidebar */}
      <aside className={`dashboard-sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setActiveView(item.id);
                  setMobileMenuOpen(false);
                }}
                className={isActive ? 'active' : ''}
              >
                <Icon className="w-5 h-5 shrink-0" />
                <span className="text">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          style={{ top: 64 }}
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden
        />
      )}

      {/* Main content */}
      <main className="dashboard-main">{renderContent()}</main>
    </div>
  );
}

function AdminDashboardHome() {
  const metrics = [
    { label: 'Total Students', value: '—', icon: GraduationCapIcon, iconBg: '#eff6ff', iconColor: '#2563eb' },
    { label: 'Active Mentors', value: '—', icon: UsersIcon, iconBg: '#f5f3ff', iconColor: '#7c3aed' },
    { label: 'Active Assessments', value: '—', icon: FileTextIcon, iconBg: '#ecfdf5', iconColor: '#059669' },
    { label: 'Pending Submissions', value: '—', icon: ClockIcon, iconBg: '#fff7ed', iconColor: '#ea580c' },
  ];

  const recentActivities = [
    { id: 1, text: 'Platform ready. Connect backend to see real data.', time: '—' },
  ];

  return (
    <div className="dashboard-section">
      <h1>Dashboard Overview</h1>
      <p className="section-desc">Welcome back. Here&apos;s a summary of your platform (connect API for live data).</p>

      <div className="metrics-grid">
        {metrics.map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="metric-card">
              <div className="metric-icon" style={{ backgroundColor: m.iconBg, color: m.iconColor }}>
                <Icon className="w-6 h-6" />
              </div>
              <div className="metric-value">{m.value}</div>
              <div className="metric-label">{m.label}</div>
            </div>
          );
        })}
      </div>

      <div className="activity-list" style={{ marginTop: '1.5rem' }}>
        <div className="p-4 border-b border-gray-200 font-medium text-gray-900">Recent Activity</div>
        {recentActivities.map((a) => (
          <div key={a.id} className="activity-item">
            <div>
              <span className="text-gray-900">{a.text}</span>
              <span className="text-gray-500 text-sm ml-2">{a.time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AdminUsersSection() {
  const [tab, setTab] = useState('students');
  const [students, setStudents] = useState([]);
  const [mentors, setMentors] = useState([]);
  const [studentPage, setStudentPage] = useState(1);
  const [mentorPage, setMentorPage] = useState(1);
  const [studentsTotalCount, setStudentsTotalCount] = useState(0);
  const [mentorsTotalCount, setMentorsTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const fetchAll = async () => {
      try {
        const [sRes, mRes] = await Promise.all([
          adminApi.getStudents({ page: studentPage }),
          adminApi.getMentors({ page: mentorPage }),
        ]);
        if (!cancelled) {
          const sData = sRes?.data;
          const mData = mRes?.data;
          const sList = Array.isArray(sData) ? sData : (sData?.results ?? []);
          const mList = Array.isArray(mData) ? mData : (mData?.results ?? []);
          setStudents(sList);
          setMentors(mList);
          setStudentsTotalCount(typeof sData?.count === 'number' ? sData.count : sList.length);
          setMentorsTotalCount(typeof mData?.count === 'number' ? mData.count : mList.length);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || err.message || 'Failed to load users');
          setStudents([]);
          setMentors([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAll();
    return () => { cancelled = true; };
  }, [studentPage, mentorPage]);

  const list = tab === 'students' ? students : mentors;
  const currentPage = tab === 'students' ? studentPage : mentorPage;
  const totalCount = tab === 'students' ? studentsTotalCount : mentorsTotalCount;
  const setCurrentPage = tab === 'students' ? setStudentPage : setMentorPage;
  const usersPerPage = 20;
  const totalPages = Math.max(1, Math.ceil(totalCount / usersPerPage));
  const roleLabel = tab === 'students' ? 'Student' : 'Mentor';

  return (
    <div className="dashboard-section">
      <h1>Users</h1>
      <p className="section-desc">Students and mentors only (admin users are not listed).</p>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button
          type="button"
          onClick={() => setTab('students')}
          style={{
            padding: '0.5rem 1rem',
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            background: tab === 'students' ? '#111827' : 'white',
            color: tab === 'students' ? 'white' : '#374151',
            cursor: 'pointer',
          }}
        >
          Students ({studentsTotalCount})
        </button>
        <button
          type="button"
          onClick={() => setTab('mentors')}
          style={{
            padding: '0.5rem 1rem',
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            background: tab === 'mentors' ? '#111827' : 'white',
            color: tab === 'mentors' ? 'white' : '#374151',
            cursor: 'pointer',
          }}
        >
          Mentors ({mentorsTotalCount})
        </button>
      </div>
      {error && <p style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</p>}
      {loading ? (
        <p style={{ color: '#6b7280' }}>Loading…</p>
      ) : (
        <div className="admin-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Username</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {list.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
                    No {tab} found.
                  </td>
                </tr>
              ) : (
                list.map((row) => {
                  const profile = tab === 'students' ? row.student_profile : row.mentor_profile;
                  const name = profile
                    ? (profile.first_name && profile.last_name ? `${profile.first_name} ${profile.last_name}` : row.username)
                    : row.username;
                  return (
                    <tr key={row.id}>
                      <td>{name}</td>
                      <td>{row.email}</td>
                      <td>{row.username}</td>
                      <td>{row.is_active ? 'Active' : 'Inactive'}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}
      {!loading && totalPages > 1 && (
        <div className="pagination-bar">
          <button type="button" disabled={currentPage <= 1} onClick={() => setCurrentPage((p) => p - 1)}>Previous</button>
          <span>Page {currentPage} of {totalPages} ({totalCount} {roleLabel}s)</span>
          <button type="button" disabled={currentPage >= totalPages} onClick={() => setCurrentPage((p) => p + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}

function AdminDomainsSection({ onDomainsChanged }) {
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingDomain, setEditingDomain] = useState(null);
  const [form, setForm] = useState({ name: '', code: '', description: '' });
  const [submitting, setSubmitting] = useState(false);
  const [domainPage, setDomainPage] = useState(1);
  const [domainsTotalCount, setDomainsTotalCount] = useState(0);

  const loadDomains = async (page = 1) => {
    try {
      const res = await adminApi.getDomainsAdmin({ page, page_size: 10 });
      const data = res?.data;
      const list = Array.isArray(data) ? data : (data?.results ?? []);
      setDomains(list);
      setDomainsTotalCount(typeof data?.count === 'number' ? data.count : list.length);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to load domains');
      setDomains([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDomains(domainPage); }, [domainPage]);

  const openAddModal = () => {
    setEditingDomain(null);
    setForm({ name: '', code: '', description: '' });
    setModalOpen(true);
  };

  const openEditModal = (d) => {
    setEditingDomain(d);
    setForm({ name: d.name || '', code: d.code || '', description: d.description || '' });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingDomain(null);
    setForm({ name: '', code: '', description: '' });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name?.trim() || !form.code?.trim()) {
      setError('Name and code are required.');
      return;
    }
    setSubmitting(true);
    setError(null);
    const payload = buildDomainPayload(form);
    try {
      if (editingDomain?.id) {
        await adminApi.updateDomain(editingDomain.id, payload);
      } else {
        await adminApi.createDomain(payload);
      }
      closeModal();
      await loadDomains(domainPage);
      onDomainsChanged?.();
    } catch (err) {
      setError(err.response?.data?.detail || (typeof err.response?.data === 'object' ? JSON.stringify(err.response.data) : err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (d) => {
    if (!window.confirm(`Delete domain "${d.name}"? This may affect questions and profiles linked to it.`)) return;
    try {
      await adminApi.deleteDomain(d.id);
      if (editingDomain?.id === d.id) closeModal();
      await loadDomains(domainPage);
      onDomainsChanged?.();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete domain');
    }
  };

  const domainsPerPage = 10;
  const domainTotalPages = Math.max(1, Math.ceil(domainsTotalCount / domainsPerPage));

  return (
    <div className="dashboard-section dashboard-section-no-scroll">
      <h1>Domains</h1>
      {error && <p style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</p>}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
        <button type="button" onClick={openAddModal} className="btn-primary" style={{ padding: '0.5rem 1rem', borderRadius: 8, background: '#059669', color: 'white', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
          Add domain
        </button>
      </div>

      {modalOpen && (
        <div className="modal-overlay" onClick={closeModal} role="dialog" aria-modal="true">
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 1rem 0' }}>{editingDomain ? 'Edit domain' : 'Add domain'}</h3>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', minWidth: 320 }}>
              <label>
                <span style={{ display: 'block', marginBottom: 4, fontSize: '0.875rem', fontWeight: 600 }}>Name</span>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Web Development"
                  required
                  style={{ width: '100%', padding: '0.5rem 0.75rem', border: '1px solid #e5e7eb', borderRadius: 8 }}
                />
              </label>
              <label>
                <span style={{ display: 'block', marginBottom: 4, fontSize: '0.875rem', fontWeight: 600 }}>Code</span>
                <input
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase().replace(/\s/g, '_') }))}
                  placeholder="e.g. WEB_DEVELOPMENT"
                  required
                  style={{ width: '100%', padding: '0.5rem 0.75rem', border: '1px solid #e5e7eb', borderRadius: 8 }}
                />
              </label>
              <label>
                <span style={{ display: 'block', marginBottom: 4, fontSize: '0.875rem', fontWeight: 600 }}>Description (optional)</span>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Short description"
                  rows={2}
                  style={{ width: '100%', padding: '0.5rem 0.75rem', border: '1px solid #e5e7eb', borderRadius: 8, resize: 'vertical' }}
                />
              </label>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button type="submit" disabled={submitting} style={{ padding: '0.5rem 1rem', background: '#059669', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>
                  {submitting ? 'Saving…' : (editingDomain ? 'Update' : 'Add domain')}
                </button>
                <button type="button" onClick={closeModal} style={{ padding: '0.5rem 1rem', background: '#6b7280', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer' }}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="admin-table-wrap admin-table-scroll">
        <div style={{ padding: '0.75rem', borderBottom: '1px solid #e5e7eb', fontWeight: 600 }}>Domains ({domainsTotalCount}) • Page {domainPage} of {domainTotalPages}</div>
        {loading ? (
          <div style={{ padding: '1rem', color: '#6b7280' }}>Loading…</div>
        ) : domains.length === 0 ? (
          <div style={{ padding: '1rem', color: '#6b7280' }}>No domains yet. Add one above.</div>
        ) : (
          <table style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Name</th>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Code</th>
                <th style={{ textAlign: 'left', padding: '0.75rem' }}>Description</th>
                <th style={{ width: 120, padding: '0.75rem' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {domains.map((d) => (
                <tr key={d.id}>
                  <td style={{ padding: '0.75rem' }}>{d.name}</td>
                  <td style={{ padding: '0.75rem' }}><code style={{ fontSize: '0.875rem' }}>{d.code}</code></td>
                  <td style={{ padding: '0.75rem', color: '#6b7280', maxWidth: 300 }}>{(d.description || '').slice(0, 80)}{(d.description || '').length > 80 ? '…' : ''}</td>
                  <td style={{ padding: '0.75rem' }}>
                    <button type="button" onClick={() => openEditModal(d)} title="Edit domain" aria-label="Edit" style={{ marginRight: 8, padding: 6, cursor: 'pointer', border: 'none', background: 'transparent', color: '#6b7280', borderRadius: 6 }}><PencilIcon className="w-4 h-4" /></button>
                    <button type="button" onClick={() => handleDelete(d)} title="Delete domain" aria-label="Delete" style={{ padding: 6, cursor: 'pointer', border: 'none', background: 'transparent', color: '#dc2626', borderRadius: 6 }}><TrashIcon className="w-4 h-4" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {domainTotalPages > 1 && (
          <div className="pagination-bar">
            <button type="button" disabled={domainPage <= 1} onClick={() => setDomainPage((p) => p - 1)}>Previous</button>
            <span>Page {domainPage} of {domainTotalPages}</span>
            <button type="button" disabled={domainPage >= domainTotalPages} onClick={() => setDomainPage((p) => p + 1)}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}

function AdminAssessmentsSection() {
  const { domains, loading: domainsLoading } = useDomains();
  const [questionCounts, setQuestionCounts] = useState([]);
  const [countsLoading, setCountsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDomainId, setSelectedDomainId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [questionForm, setQuestionForm] = useState({
    text: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_option: 'A', complexity: 'MEDIUM', order: 0, points: 1,
  });
  const [questionSubmitting, setQuestionSubmitting] = useState(false);
  const [questionModalOpen, setQuestionModalOpen] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState(null);
  const [questionPage, setQuestionPage] = useState(1);
  const [questionsTotalCount, setQuestionsTotalCount] = useState(0);

  const openAddQuestionModal = () => {
    setEditingQuestion(null);
    setQuestionForm({ text: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_option: 'A', complexity: 'MEDIUM', order: questionsTotalCount, points: 1 });
    setQuestionModalOpen(true);
  };

  const openEditQuestionModal = (q) => {
    setEditingQuestion(q);
    setQuestionForm({
      text: q.text || '', option_a: q.option_a || '', option_b: q.option_b || '', option_c: q.option_c || '', option_d: q.option_d || '',
      correct_option: q.correct_option || 'A', complexity: q.complexity || 'MEDIUM', order: q.order ?? 0, points: q.points ?? 1,
    });
    setQuestionModalOpen(true);
  };

  const closeQuestionModal = () => {
    setQuestionModalOpen(false);
    setEditingQuestion(null);
    setQuestionForm({ text: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_option: 'A', complexity: 'MEDIUM', order: 0, points: 1 });
  };

  const loadQuestionCounts = async () => {
    try {
      const res = await adminApi.getDomainQuestionCounts();
      setQuestionCounts(Array.isArray(res.data) ? res.data : []);
      setError(null);
    } catch (err) {
      setQuestionCounts([]);
    } finally {
      setCountsLoading(false);
    }
  };

  useEffect(() => {
    loadQuestionCounts();
  }, []);

  useEffect(() => {
    if (!selectedDomainId) {
      setQuestions([]);
      setQuestionsTotalCount(0);
      return;
    }
    setQuestionPage(1);
  }, [selectedDomainId]);

  useEffect(() => {
    if (!selectedDomainId) return;
    setQuestionsLoading(true);
    adminApi.getDomainQuestions(selectedDomainId, { page: questionPage })
      .then((res) => {
        const data = res?.data;
        const list = Array.isArray(data) ? data : (data?.results ?? []);
        setQuestions(list);
        setQuestionsTotalCount(typeof data?.count === 'number' ? data.count : list.length);
      })
      .catch(() => { setQuestions([]); setQuestionsTotalCount(0); })
      .finally(() => setQuestionsLoading(false));
  }, [selectedDomainId, questionPage]);

  const handleSubmitQuestion = async (e) => {
    e.preventDefault();
    if (!selectedDomainId) return;
    setQuestionSubmitting(true);
    const payload = buildQuestionPayload(questionForm, editingQuestion, questionsTotalCount);
    try {
      if (editingQuestion?.id) {
        await adminApi.updateQuestion(selectedDomainId, editingQuestion.id, payload);
      } else {
        await adminApi.createQuestion(selectedDomainId, payload);
      }
      closeQuestionModal();
      const res = await adminApi.getDomainQuestions(selectedDomainId, { page: questionPage });
      const data = res?.data;
      setQuestions(Array.isArray(data) ? data : (data?.results ?? []));
      if (typeof data?.count === 'number') setQuestionsTotalCount(data.count);
      await loadQuestionCounts();
    } catch (err) {
      setError(err.response?.data || err.message);
    } finally {
      setQuestionSubmitting(false);
    }
  };

  const handleDeleteQuestion = async (q) => {
    if (!selectedDomainId || !window.confirm('Are you sure you want to delete this question?')) return;
    try {
      await adminApi.deleteQuestion(selectedDomainId, q.id);
      if (editingQuestion?.id === q.id) closeQuestionModal();
      const res = await adminApi.getDomainQuestions(selectedDomainId, { page: questionPage });
      const data = res?.data;
      setQuestions(Array.isArray(data) ? data : (data?.results ?? []));
      if (typeof data?.count === 'number') setQuestionsTotalCount(data.count);
      await loadQuestionCounts();
    } catch (err) {
      setError(err.response?.data || err.message);
    }
  };

  const questionsPerPage = 5;
  const questionTotalPages = Math.max(1, Math.ceil(questionsTotalCount / questionsPerPage));

  const domainsList = Array.isArray(domains) ? domains : [];
  const domainQuestionCount = (domainId) => {
    const c = questionCounts.find((x) => Number(x.domain_id) === Number(domainId));
    return c?.question_count ?? 0;
  };
  const selectedDomain = domainsList.find((d) => Number(d.id) === Number(selectedDomainId));

  return (
    <div className="dashboard-section">
      <h1>Domain Questions</h1>
      <p className="section-desc">
        Add MCQ questions per domain. When a student takes the test, they get random questions from their target domain(s). One question bank per domain.
      </p>
      {error && typeof error === 'object' && (
        <pre style={{ color: '#dc2626', marginBottom: '1rem', fontSize: 12 }}>{JSON.stringify(error, null, 2)}</pre>
      )}
      {error && typeof error === 'string' && <p style={{ color: '#dc2626', marginBottom: '1rem' }}>{error}</p>}

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '1.5rem' }}>
        <div className="admin-table-wrap">
          <div style={{ padding: '0.75rem', borderBottom: '1px solid #e5e7eb', fontWeight: 600 }}>Domains</div>
          {domainsLoading || countsLoading ? (
            <div style={{ padding: '1rem', color: '#6b7280' }}>Loading…</div>
          ) : domainsList.length === 0 ? (
            <div style={{ padding: '1rem', color: '#6b7280' }}>No domains. Run backend: python manage.py populate_domains</div>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {domainsList.map((d) => (
                <li key={d.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedDomainId(d.id)}
                    style={{
                      width: '100%',
                      padding: '0.75rem 1rem',
                      textAlign: 'left',
                      border: 'none',
                      borderBottom: '1px solid #e5e7eb',
                      background: Number(selectedDomainId) === Number(d.id) ? '#f3f4f6' : 'white',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ fontWeight: 500 }}>{d.name}</div>
                    <div style={{ fontSize: 12, color: '#6b7280' }}>{domainQuestionCount(d.id)} questions</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          {selectedDomainId && (
            <>
              {questionsLoading ? (
                <p style={{ color: '#6b7280' }}>Loading questions…</p>
              ) : (
                <>
              <div className="domain-questions-header">
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.125rem' }}>{selectedDomain?.name || 'Domain'} – Question bank</h3>
                </div>
                <button type="button" onClick={openAddQuestionModal} className="btn-primary-green">
                  Add question
                </button>
              </div>

              {questionModalOpen && (
                <div className="modal-overlay" onClick={closeQuestionModal} role="dialog" aria-modal="true">
                  <div className="modal-card modal-card-mcq" onClick={(e) => e.stopPropagation()}>
                    <h3 style={{ margin: '0 0 1rem 0' }}>{editingQuestion ? 'Edit question' : 'Add question'}</h3>
                    <div className="mcq-editor-card mcq-editor-card-in-modal">
                      <form onSubmit={handleSubmitQuestion}>
                      <div className="mcq-field-group">
                        <label className="mcq-label">Question text</label>
                        <textarea
                          className="mcq-textarea"
                          placeholder="Enter your question here..."
                          value={questionForm.text}
                          onChange={(e) => setQuestionForm((f) => ({ ...f, text: e.target.value }))}
                          required
                          rows={4}
                        />
                      </div>
                      <div className="mcq-field-group">
                        <label className="mcq-label">Answer options</label>
                        <div className="mcq-options-grid">
                          {['A', 'B', 'C', 'D'].map((opt) => (
                            <input
                              key={opt}
                              type="text"
                              className="mcq-input"
                              placeholder={`Option ${opt}`}
                              value={questionForm[`option_${opt.toLowerCase()}`]}
                              onChange={(e) => setQuestionForm((f) => ({ ...f, [`option_${opt.toLowerCase()}`]: e.target.value }))}
                            />
                          ))}
                        </div>
                      </div>
                      <div className="mcq-settings-row mcq-field-group">
                        <div className="mcq-field">
                          <label className="mcq-label">Correct</label>
                          <select
                            className="mcq-input"
                            value={questionForm.correct_option}
                            onChange={(e) => setQuestionForm((f) => ({ ...f, correct_option: e.target.value }))}
                          >
                            {['A', 'B', 'C', 'D'].map((o) => (
                              <option key={o} value={o}>{o}</option>
                            ))}
                          </select>
                        </div>
                        <div className="mcq-field">
                          <label className="mcq-label">Complexity</label>
                          <select
                            className="mcq-input"
                            value={questionForm.complexity}
                            onChange={(e) => setQuestionForm((f) => ({ ...f, complexity: e.target.value }))}
                          >
                            <option value="EASY">Easy</option>
                            <option value="MEDIUM">Medium</option>
                            <option value="HARD">Hard</option>
                          </select>
                        </div>
                        <div className="mcq-field mcq-field-points">
                          <label className="mcq-label">Points</label>
                          <input
                            type="number"
                            className="mcq-input"
                            min={1}
                            value={questionForm.points}
                            onChange={(e) => setQuestionForm((f) => ({ ...f, points: e.target.value }))}
                          />
                        </div>
                      </div>
                      <div className="mcq-modal-actions">
                        <button type="submit" className="mcq-btn-add" disabled={questionSubmitting}>
                          {questionSubmitting ? (editingQuestion ? 'Updating…' : 'Adding…') : (editingQuestion ? 'Update' : 'Add question')}
                        </button>
                        <button type="button" className="mcq-btn-cancel" onClick={closeQuestionModal}>
                          Cancel
                        </button>
                      </div>
                    </form>
                    </div>
                  </div>
                </div>
              )}

              <div style={{ marginBottom: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 className="mcq-title" style={{ margin: 0, fontSize: '1rem' }}>Questions</h2>
                <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                  {questionsTotalCount} total • Page {questionPage} of {questionTotalPages}
                </span>
              </div>
              <div className="mcq-questions-card">
                {questions.length === 0 ? (
                  <div className="mcq-list-empty">No questions yet. Click “Add question” to create one.</div>
                ) : (
                  <>
                    <div className="mcq-list-header">
                      <span>Question</span>
                      <span>Complexity</span>
                      <span>Points</span>
                      <span>Order</span>
                      <span>Actions</span>
                    </div>
                    {questions.map((q) => {
                      const complexityLabel = q.complexity === 'EASY' ? 'Easy' : q.complexity === 'HARD' ? 'Hard' : 'Medium';
                      const badgeClass = q.complexity === 'EASY' ? 'mcq-badge-easy' : q.complexity === 'HARD' ? 'mcq-badge-hard' : 'mcq-badge-medium';
                      const opts = [
                        ['A', q.option_a],
                        ['B', q.option_b],
                        ['C', q.option_c],
                        ['D', q.option_d],
                      ];
                      return (
                        <div key={q.id} className="mcq-list-row">
                          <div className="mcq-question-cell">
                            <p className="mcq-question-preview">{q.text || ''}</p>
                            <div className="mcq-options-list">
                              {opts.map(([letter, text]) => (
                                <span key={letter} className={q.correct_option === letter ? 'mcq-option correct' : 'mcq-option'}>
                                  {letter}: {String(text || '').slice(0, 40)}{String(text || '').length > 40 ? '…' : ''}
                                </span>
                              ))}
                              <span className="mcq-correct-label">Correct: {q.correct_option}</span>
                            </div>
                          </div>
                          <span className={`mcq-badge ${badgeClass}`}>{complexityLabel}</span>
                          <span className="mcq-badge mcq-badge-points">{q.points}</span>
                          <span style={{ fontSize: '0.875rem', color: '#4b5563' }}>#{(q.order ?? 0) + 1}</span>
                          <div className="mcq-row-actions">
                            <button type="button" className="mcq-btn-icon" title="Edit question" aria-label="Edit" onClick={() => openEditQuestionModal(q)}><PencilIcon className="w-4 h-4" /></button>
                            <button type="button" className="mcq-btn-icon mcq-btn-delete" title="Delete question" aria-label="Delete" onClick={() => handleDeleteQuestion(q)}><TrashIcon className="w-4 h-4" /></button>
                          </div>
                        </div>
                      );
                    })}
                  </>
                )}
                {questionTotalPages > 1 && (
                  <div className="pagination-bar">
                    <button type="button" disabled={questionPage <= 1} onClick={() => setQuestionPage((p) => p - 1)}>Previous</button>
                    <span>Page {questionPage} of {questionTotalPages}</span>
                    <button type="button" disabled={questionPage >= questionTotalPages} onClick={() => setQuestionPage((p) => p + 1)}>Next</button>
                  </div>
                )}
              </div>
                </>
              )}
            </>
          )}
          {!selectedDomainId && <p style={{ color: '#6b7280' }}>Select a domain to add questions.</p>}
        </div>
      </div>
    </div>
  );
}

function AdminProjectsPlaceholder() {
  return (
    <div className="dashboard-section">
      <h1>Project Templates</h1>
      <p className="section-desc">Define, upload, and update project templates and evaluation criteria (FR10).</p>
      <div className="info-card" style={{ marginTop: '1rem' }}>
        <p>Add project templates with title, domain, complexity, and evaluation criteria. These feed into task allocation (FR3) and student tasks.</p>
        <button type="button" className="btn-primary mt-4" style={{ padding: '0.5rem 1rem', borderRadius: 8, background: '#111827', color: 'white', border: 'none', cursor: 'pointer' }}>
          Add Template (API required)
        </button>
      </div>
    </div>
  );
}

function AdminReportsPlaceholder() {
  return (
    <div className="dashboard-section">
      <h1>Reports & Analytics</h1>
      <p className="section-desc">Progress tracking and skill improvement insights (FR9).</p>
      <div className="info-card" style={{ marginTop: '1rem' }}>
        <p>Charts and tables for signups, completions, and skill improvement over time. Filter by date range and role.</p>
        <button type="button" className="btn-primary mt-4" style={{ padding: '0.5rem 1rem', borderRadius: 8, background: '#111827', color: 'white', border: 'none', cursor: 'pointer' }}>
          Export Report (API required)
        </button>
      </div>
    </div>
  );
}

export default AdminDashboard;
