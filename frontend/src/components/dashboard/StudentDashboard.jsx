/**
 * Student Dashboard – FR2 skill assessment (composed MCQs, AI-recommended domain), tasks, career chatbot.
 */
import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { studentApi } from '../../api/student.api';
import { getDomains } from '../../api/domains.api';
import { buildProfileUpdatePayload, buildAssessmentSubmitPayload } from '../../services/student.service';
import { getErrorMessage } from '../../utilities/authUtils';
import {
  GraduationCapIcon,
  LayoutDashboardIcon,
  CheckSquareIcon,
  FolderOpenIcon,
  BellIcon,
  MessageCircleIcon,
  LogOutIcon,
  AlertCircleIcon,
  CheckCircleIcon,
  LockIcon,
  TargetIcon,
  AwardIcon,
  SendIcon,
  FileTextIcon,
  UserIcon,
  ClockIcon,
  ChevronRightIcon,
  XCircleIcon,
  BarChartIcon,
  ArrowLeftIcon,
} from '../ui/Icons';
import './Dashboard.css';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboardIcon },
  { id: 'tasks', label: 'My Tasks', icon: CheckSquareIcon },
  { id: 'portfolio', label: 'Portfolio', icon: FolderOpenIcon },
];

const CHATBOT_SUGGESTIONS = [
  'How do I start freelancing?',
  'What skills are in demand?',
  'Tips for building a portfolio',
];

function getBotReply(input) {
  const lower = (input || '').toLowerCase();
  if (lower.includes('freelanc') || lower.includes('start')) return 'To start freelancing: 1) Build a strong portfolio. 2) Create profiles on Upwork, Fiverr. 3) Start with smaller projects. 4) Network and ask for referrals.';
  if (lower.includes('skill') || lower.includes('demand')) return 'High-demand skills: Web Dev (React, Next.js), Mobile (React Native, Flutter), UI/UX, Data Science, Cloud (AWS, Azure), Cybersecurity.';
  if (lower.includes('portfolio')) return 'Portfolio tips: Quality over quantity, include case studies, live demos or GitHub links, keep it updated.';
  return 'I can help with freelancing tips, career advice, and skill development. Ask something specific!';
}

/* Figma-style: Start screen before quiz – Back allowed here; no back once quiz starts */
function AssessmentStartScreen({ onStart, onBack, attemptCount, maxAttempts }) {
  return (
    <div className="quiz-screen-wrap">
      <div className="quiz-card quiz-card-no-scroll" style={{ maxWidth: '36rem', position: 'relative' }}>
        {onBack && (
          <button type="button" onClick={onBack} className="quiz-back-btn" style={{ position: 'absolute', top: '1rem', left: '1rem', display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.5rem 0.75rem', background: 'transparent', border: '1px solid #e5e7eb', borderRadius: 8, cursor: 'pointer', color: '#374151', fontSize: '0.875rem' }} aria-label="Back to Dashboard">
            <ArrowLeftIcon className="w-4 h-4" /> Back
          </button>
        )}
        <div className="quiz-start-icon">
          <FileTextIcon className="w-8 h-8" />
        </div>
        <h2 className="quiz-start-title">Skill Assessment</h2>
        <p className="quiz-start-subtitle">Test your knowledge and demonstrate your skills</p>

        <div className="quiz-start-row">
          <FileTextIcon className="w-5 h-5 quiz-start-row-icon" />
          <div>
            <h3>Questions</h3>
            <p>20 to 30 multiple choice questions covering key concepts</p>
          </div>
        </div>
        <div className="quiz-start-row">
          <ClockIcon className="w-5 h-5 quiz-start-row-icon" />
          <div>
            <h3>Time Limit</h3>
            <p>60 seconds per question – answer within the time limit</p>
          </div>
        </div>
        <div className="quiz-start-row">
          <TargetIcon className="w-5 h-5 quiz-start-row-icon" />
          <div>
            <h3>Passing Score</h3>
            <p>70% or higher required to pass the assessment</p>
          </div>
        </div>

        <div className="quiz-note-box">
          <p><strong>Note:</strong> Once you start, you cannot pause the assessment. Make sure you have a stable internet connection and won&apos;t be interrupted.</p>
        </div>

        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '1rem' }}>Attempt {attemptCount + 1} of {maxAttempts}</p>
        <div style={{ display: 'flex', gap: '0.75rem', flexDirection: 'column' }}>
          <button type="button" className="quiz-btn-primary" onClick={onStart}>Start Assessment</button>
          {onBack && (
            <button type="button" onClick={onBack} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.5rem', background: 'transparent', border: '1px solid #e5e7eb', borderRadius: 8, cursor: 'pointer', color: '#6b7280', fontSize: '0.875rem' }}>
              <ArrowLeftIcon className="w-4 h-4" /> Back to Dashboard
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* Figma-style: One question per page with timer */
function AssessmentQuizView({ questions, selectedAnswers, onSelectAnswer, currentIndex, onNext, onSubmit, loading, error }) {
  const [timeLeft, setTimeLeft] = React.useState(60);
  const currentQuestion = questions[currentIndex];
  const isLast = currentIndex === questions.length - 1;
  const hasAnswered = selectedAnswers[currentIndex] != null;

  React.useEffect(() => {
    setTimeLeft(60);
  }, [currentIndex]);

  React.useEffect(() => {
    if (timeLeft <= 0) {
      if (isLast) onSubmit();
      else onNext();
      return;
    }
    const t = setInterval(() => setTimeLeft((prev) => prev - 1), 1000);
    return () => clearInterval(t);
  }, [timeLeft, isLast, onNext, onSubmit]);

  // Blue ring = remaining time: full at 60s, depletes to empty at 0s
  const circumference = 2 * Math.PI * 34;
  const progress = (timeLeft / 60) * 100;
  const strokeDashoffset = circumference * (1 - progress / 100);
  const isLowTime = timeLeft < 10;
  const options = ['A', 'B', 'C', 'D'].map((opt) => ({ letter: opt, text: currentQuestion[`option_${opt.toLowerCase()}`] }));

  return (
    <div className="quiz-screen-wrap">
      <div className="quiz-card quiz-card-wide">
        {error && (
          <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, color: '#991b1b', fontSize: '0.875rem' }}>{error}</div>
        )}
        <div className="quiz-progress-row">
          <div>
            <div className="quiz-progress-label">Progress</div>
            <div className="quiz-progress-text">Question {currentIndex + 1} of {questions.length}</div>
          </div>
          <div className="quiz-timer-wrap">
            <svg className="quiz-timer-svg" viewBox="0 0 80 80" aria-label={`${timeLeft} seconds left`}>
              <circle cx="40" cy="40" r="34" fill="none" stroke="#e5e7eb" strokeWidth="6" />
              <circle
                cx="40" cy="40" r="34"
                fill="none"
                stroke={isLowTime ? '#dc2626' : '#2563eb'}
                strokeWidth="6"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{ transition: 'stroke-dashoffset 1s linear' }}
              />
            </svg>
            <div className="quiz-timer-value">
              <span className={`quiz-timer-num ${isLowTime ? 'low' : 'normal'}`}>{timeLeft}</span>
              <span className="quiz-timer-sec">sec</span>
            </div>
          </div>
        </div>

        <div className="quiz-question-text">{currentQuestion.text}</div>
        <div className="quiz-options-list">
          {options.map(({ letter, text }) => {
            const isSelected = selectedAnswers[currentIndex] === letter;
            return (
              <button
                key={letter}
                type="button"
                className={`quiz-option-btn ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectAnswer(currentIndex, letter)}
              >
                <div className="quiz-option-inner">
                  <div className="quiz-option-letter">{letter}</div>
                  <span>{text || ''}</span>
                </div>
              </button>
            );
          })}
        </div>

        <div className="quiz-nav-row">
          <span className="quiz-answered-count">
            {selectedAnswers.filter((a) => a != null).length} of {questions.length} answered
          </span>
          {isLast ? (
            <button type="button" className="quiz-btn-next primary" onClick={onSubmit} disabled={!hasAnswered || loading}>
              {loading ? 'Submitting…' : 'Submit Assessment'}
            </button>
          ) : (
            <button type="button" className="quiz-btn-next primary" onClick={onNext} disabled={!hasAnswered}>
              Next <ChevronRightIcon className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const PASSING_PERCENT = 70;
const MIN_DOMAINS = 2;
const MAX_DOMAINS = 3;

function SelectDomainsCard({ onSaved, refreshUser, initialSelectedIds = [] }) {
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedIds, setSelectedIds] = useState(Array.isArray(initialSelectedIds) ? initialSelectedIds : []);
  const [error, setError] = useState(null);

  useEffect(() => {
    getDomains()
      .then((list) => setDomains(Array.isArray(list) ? list : []))
      .catch(() => setError('Failed to load domains'))
      .finally(() => setLoading(false));
  }, []);

  const toggle = (id) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= MAX_DOMAINS) return prev;
      return [...prev, id];
    });
  };

  const handleSave = () => {
    if (selectedIds.length < MIN_DOMAINS) {
      setError(`Select at least ${MIN_DOMAINS} and up to ${MAX_DOMAINS} domains.`);
      return;
    }
    setError(null);
    setSaving(true);
    studentApi.updateProfile(buildProfileUpdatePayload(selectedIds))
      .then(() => {
        if (typeof refreshUser === 'function') refreshUser();
        if (typeof onSaved === 'function') onSaved();
      })
      .catch((err) => setError(err.response?.data?.detail || err.message || 'Failed to save'))
      .finally(() => setSaving(false));
  };

  if (loading) return <div className="info-card" style={{ padding: '2rem' }}>Loading domains…</div>;
  return (
    <div className="assessment-cta-block">
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1.5rem' }}>
        <div style={{ padding: '1rem', borderRadius: 12, background: '#eff6ff', color: '#2563eb' }}>
          <TargetIcon className="w-8 h-8" />
        </div>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem', color: '#111827' }}>Select your domains of interest</h2>
          <p style={{ color: '#374151', marginBottom: '1rem' }}>
            Choose 2 to 3 domains you want to focus on. Then you can take the skill assessment to get a recommended domain.
          </p>
          {error && <p style={{ color: '#dc2626', marginBottom: '0.5rem', fontSize: '0.875rem' }}>{error}</p>}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
            {domains.map((d) => (
              <label key={d.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.5rem 0.75rem', background: selectedIds.includes(d.id) ? '#eff6ff' : '#f3f4f6', border: `2px solid ${selectedIds.includes(d.id) ? '#2563eb' : '#e5e7eb'}`, borderRadius: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={selectedIds.includes(d.id)} onChange={() => toggle(d.id)} />
                <span>{d.name}</span>
              </label>
            ))}
          </div>
          <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '0.75rem' }}>{selectedIds.length} of {MAX_DOMAINS} selected (min {MIN_DOMAINS})</p>
          <button type="button" className="btn-start-assessment" onClick={handleSave} disabled={saving || selectedIds.length < MIN_DOMAINS}>
            {saving ? 'Saving…' : 'Save domains'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* Figma-style: Results screen */
function AssessmentResultView({ result, onBack }) {
  const percentage = result.percentage ?? 0;
  const passed = result.passed ?? percentage >= PASSING_PERCENT;
  const score = result.score ?? 0;
  const totalPoints = result.total_points ?? 0;
  const questionCount = result.question_count ?? (result.answers?.length ?? 0);
  const correctCount = result.correct_count ?? (questionCount ? score : 0);
  const displayTotal = questionCount > 0 ? questionCount : totalPoints;
  const displayCorrect = questionCount > 0 ? correctCount : score;
  const recommended = result.recommended_domains?.[0];

  return (
    <div className="quiz-screen-wrap">
      <div className="quiz-card" style={{ maxWidth: '36rem' }}>
        <div className={`quiz-results-icon-wrap ${passed ? 'passed' : 'failed'}`}>
          {passed ? <CheckCircleIcon className="w-10 h-10" /> : <XCircleIcon className="w-10 h-10" />}
        </div>
        <h2 className="quiz-results-title">Assessment Complete</h2>
        <p className="quiz-results-subtitle">
          {passed ? 'Congratulations! You passed the assessment.' : 'You did not meet the passing criteria this time.'}
        </p>

        <div className="quiz-score-card">
          <div className="quiz-score-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BarChartIcon className="w-5 h-5" style={{ color: '#2563eb' }} />
              <span style={{ fontWeight: 500, color: '#111827' }}>Your Score</span>
            </div>
            <span className={`quiz-score-badge ${passed ? 'passed' : 'failed'}`}>{passed ? 'PASSED' : 'FAILED'}</span>
          </div>
          <div style={{ marginBottom: '0.5rem' }}>
            <span className="quiz-score-percent">{percentage}%</span>
            <span className="quiz-score-detail">({displayCorrect} / {displayTotal} questions)</span>
          </div>
          <div className="quiz-score-bar">
            <div className="quiz-score-bar-fill" style={{ width: `${Math.min(100, percentage)}%`, background: passed ? '#16a34a' : '#dc2626' }} />
          </div>
        </div>

        <div className="quiz-results-row">
          <span>Correct Answers</span>
          <span className="correct">{displayCorrect}</span>
        </div>
        <div className="quiz-results-row">
          <span>Incorrect Answers</span>
          <span className="incorrect">{displayTotal - displayCorrect}</span>
        </div>
        <div className="quiz-results-row">
          <span>Passing Score</span>
          <span>70%</span>
        </div>

        {passed && recommended && (
          <div className="quiz-note-box" style={{ marginTop: '1rem' }}>
            <p><strong>Your recommended domain:</strong> {recommended.name}</p>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem' }}>This domain has been added to your profile.</p>
          </div>
        )}

        {!passed && (
          <div className="quiz-retry-note">
            <p>{result.message || 'Score below 70%. Take the test again. You have 2 attempts per day.'}</p>
          </div>
        )}

        <button type="button" className="quiz-btn-primary" onClick={onBack} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
          <ArrowLeftIcon className="w-4 h-4" /> Back to Dashboard
        </button>
      </div>
    </div>
  );
}

function StudentDashboard() {
  const { user, logout, refreshUser } = useAuth();
  const [activeView, setActiveView] = useState('dashboard');
  const [assessmentPassed, setAssessmentPassed] = useState(false);
  const [, setAttemptCount] = useState(0);
  const [attemptCountToday, setAttemptCountToday] = useState(0); // from attempts list, for "X of 2 used today"
  const [lastAttempt, setLastAttempt] = useState(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showChatbot, setShowChatbot] = useState(false);
  const [assessmentView, setAssessmentView] = useState('idle'); // 'idle' | 'intro' | 'test' | 'result'
  const [composedData, setComposedData] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState([]); // array of 'A'|'B'|'C'|'D'|null by question index
  const [submitLoading, setSubmitLoading] = useState(false);
  const [assessmentError, setAssessmentError] = useState(null);
  const [result, setResult] = useState(null);
  const [resultReviewing, setResultReviewing] = useState(false);
  const [pendingResult, setPendingResult] = useState(null);
  const [tasksCompleted] = useState(0); // real data: replace with API when available

  const loadAttempts = () => {
    studentApi.getAttempts()
      .then((res) => {
        const data = res.data || {};
        const list = Array.isArray(data) ? data : (data.results || []);
        setAttemptCount(list.length);
        const today = new Date().toISOString().slice(0, 10);
        const todayCount = list.filter((a) => {
          if (!a.submitted_at) return false;
          const d = new Date(a.submitted_at).toISOString().slice(0, 10);
          return d === today;
        }).length;
        setAttemptCountToday(todayCount);
        const passed = list.some((a) => (a.score / (a.total_points || 1)) * 100 >= 70);
        setAssessmentPassed(passed);
        // Always keep latest attempt so we can show "previous recommendation" when user changed domains
        if (list.length > 0) setLastAttempt(list[0]);
      })
      .catch(() => {});
  };

  const targetDomainKey = (user?.student_profile?.target_domains ?? []).map((d) => d.id).sort().join(',');
  useEffect(() => {
    loadAttempts();
  }, [targetDomainKey]);

  const handleLogout = async () => {
    await logout();
    window.location.href = '/';
  };

  const studentName = user?.student_profile?.first_name && user?.student_profile?.last_name
    ? `${user.student_profile.first_name} ${user.student_profile.last_name}`
    : user?.username || 'Student';
  const targetDomains = user?.student_profile?.target_domains?.length > 0
    ? user.student_profile.target_domains.map((d) => d.name)
    : ['Your domains'];

  const handleStartAssessment = () => {
    setAssessmentError(null);
    setResult(null);
    setSelectedAnswers([]);
    setCurrentQuestionIndex(0);
    studentApi.getComposedAssessment()
      .then((res) => {
        setComposedData(res.data);
        setAssessmentView('intro');
      })
      .catch((err) => {
        setAssessmentError(err.response?.data?.error || err.message || 'Failed to load assessment.');
      });
  };

  const handleStartQuiz = () => {
    if (!composedData?.questions?.length) return;
    setSelectedAnswers(Array(composedData.questions.length).fill(null));
    setCurrentQuestionIndex(0);
    setAssessmentView('test');
  };

  const handleSelectAnswer = (questionIndex, optionLetter) => {
    setSelectedAnswers((prev) => {
      const next = [...prev];
      next[questionIndex] = optionLetter;
      return next;
    });
  };

  const handleNextQuestion = () => {
    setCurrentQuestionIndex((prev) => Math.min(prev + 1, (composedData?.questions?.length ?? 1) - 1));
  };

  const REVIEW_DELAY_MS = 4000;

  const handleSubmitAssessment = () => {
    if (!composedData?.questions?.length) return;
    setSubmitLoading(true);
    studentApi.submitComposedAssessmentML(
      buildAssessmentSubmitPayload(composedData.questions, selectedAnswers)
    )
      .then((res) => {
        setPendingResult(res.data);
        setResultReviewing(true);
        setAttemptCount((c) => c + 1);
        if (res.data.percentage >= PASSING_PERCENT) {
          setAssessmentPassed(true);
          if (res.data.recommended_domains?.[0]) setLastAttempt({ ...res.data, recommended_domains: res.data.recommended_domains });
          if (typeof refreshUser === 'function') refreshUser();
        }
      })
      .catch((err) => {
        setAssessmentError(getErrorMessage(err.response?.data) || err.message || 'Submit failed.');
      })
      .finally(() => setSubmitLoading(false));
  };

  useEffect(() => {
    if (!resultReviewing || !pendingResult) return;
    const t = setTimeout(() => {
      setResult(pendingResult);
      setAssessmentView('result');
      setResultReviewing(false);
      setPendingResult(null);
    }, REVIEW_DELAY_MS);
    return () => clearTimeout(t);
  }, [resultReviewing, pendingResult]);

  const handleBackToDashboard = () => {
    setAssessmentView('idle');
    setComposedData(null);
    setResult(null);
    setPendingResult(null);
    setResultReviewing(false);
    setSelectedAnswers([]);
    setCurrentQuestionIndex(0);
    setAssessmentError(null);
    loadAttempts();
    if (typeof refreshUser === 'function') refreshUser();
  };

  const renderContent = () => {
    if (assessmentView === 'intro' && composedData) {
      return (
        <AssessmentStartScreen
          onStart={handleStartQuiz}
          onBack={handleBackToDashboard}
          attemptCount={composedData.attempt_count ?? 0}
          maxAttempts={composedData.max_attempts ?? 2}
        />
      );
    }
    if (resultReviewing) {
      return (
        <div className="quiz-screen-wrap">
          <div className="quiz-card flex flex-col items-center justify-center gap-6 py-12" style={{ maxWidth: '28rem' }}>
            <div className="w-14 h-14 rounded-full border-4 border-teal-200 border-t-teal-600 animate-spin" />
            <h3 className="text-xl font-semibold text-gray-800">Reviewing your test</h3>
            <p className="text-gray-600 text-sm text-center">Please wait a moment while we prepare your results.</p>
          </div>
        </div>
      );
    }
    if (assessmentView === 'test' && composedData?.questions?.length) {
      return (
        <AssessmentQuizView
          questions={composedData.questions}
          selectedAnswers={selectedAnswers}
          onSelectAnswer={handleSelectAnswer}
          currentIndex={currentQuestionIndex}
          onNext={handleNextQuestion}
          onSubmit={handleSubmitAssessment}
          loading={submitLoading}
          error={assessmentError}
        />
      );
    }
    if (assessmentView === 'result' && result) {
      return (
        <AssessmentResultView
          result={result}
          onBack={handleBackToDashboard}
        />
      );
    }
    const lastAttemptTargetIds = (lastAttempt?.test_domains ?? []).map((d) => d.id).sort().join(',');
        const hasRecommendationForCurrentDomains = Boolean(lastAttempt?.recommended_domains?.[0] && lastAttemptTargetIds === targetDomainKey);

        switch (activeView) {
      case 'dashboard':
        return (
          <StudentDashboardHome
            studentName={studentName}
            targetDomains={targetDomains}
            assessmentPassed={assessmentPassed}
            lastAttempt={lastAttempt}
            hasRecommendationForCurrentDomains={hasRecommendationForCurrentDomains}
            attemptCount={attemptCountToday}
            attemptCountLabel="used today"
            maxAttemptsPerDay={2}
            tasksCompleted={tasksCompleted}
            onStartAssessment={handleStartAssessment}
            assessmentError={assessmentError}
          />
        );
      case 'tasks':
        return <StudentTasksPlaceholder assessmentPassed={assessmentPassed} onStartAssessment={() => setActiveView('dashboard')} />;
      case 'portfolio':
        return <StudentPortfolioPlaceholder />;
      case 'profile':
        return (
          <div className="dashboard-section">
            <h1 style={{ marginBottom: '0.25rem', color: '#111827', fontSize: '1.5rem' }}>Profile</h1>
            <p className="section-desc" style={{ marginBottom: '1.5rem', color: '#6b7280', fontSize: '0.875rem' }}>View and update your profile and target domains.</p>

            {/* Profile data card */}
            <div className="info-card" style={{ marginBottom: '1.5rem', padding: '1.25rem 1.5rem', background: 'white', borderRadius: 12, border: '1px solid #e5e7eb', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
              <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', fontWeight: 600, color: '#111827', borderBottom: '1px solid #e5e7eb', paddingBottom: '0.5rem' }}>Your information</h3>
              <div style={{ display: 'grid', gap: '0.75rem', fontSize: '0.875rem' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem 1rem' }}>
                  <span style={{ color: '#6b7280', minWidth: 100 }}>Name</span>
                  <span style={{ color: '#111827', fontWeight: 500 }}>
                    {user?.student_profile?.first_name} {user?.student_profile?.last_name}
                  </span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem 1rem' }}>
                  <span style={{ color: '#6b7280', minWidth: 100 }}>Email</span>
                  <span style={{ color: '#111827' }}>{user?.email ?? '—'}</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem 1rem' }}>
                  <span style={{ color: '#6b7280', minWidth: 100 }}>Skill level</span>
                  <span style={{ color: '#111827' }}>{user?.student_profile?.current_skill_level || 'Not set'}</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem 1rem', alignItems: 'flex-start' }}>
                  <span style={{ color: '#6b7280', minWidth: 100 }}>Target domains</span>
                  <span style={{ color: '#111827' }}>
                    {targetDomains.length > 0 && targetDomains[0] !== 'Your domains'
                      ? targetDomains.join(', ')
                      : 'None selected'}
                  </span>
                </div>
                {lastAttempt?.recommended_domains?.[0] && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem 1rem' }}>
                    <span style={{ color: '#6b7280', minWidth: 100 }}>Recommended domain</span>
                    <span style={{ color: '#047857', fontWeight: 500 }}>{lastAttempt.recommended_domains[0].name}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Edit target domains */}
            <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem', fontWeight: 600, color: '#111827' }}>Edit target domains</h3>
            <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '1rem' }}>Select 2 to 3 domains to take the skill assessment.</p>
            <SelectDomainsCard
              refreshUser={refreshUser}
              initialSelectedIds={user?.student_profile?.target_domains?.map((d) => d.id) ?? []}
              onSaved={() => setActiveView('dashboard')}
            />
            <button type="button" onClick={() => setActiveView('dashboard')} style={{ marginTop: '1.5rem', padding: '0.5rem 1rem', border: '1px solid #e5e7eb', background: 'white', borderRadius: 8, cursor: 'pointer', color: '#374151', fontSize: '0.875rem' }}>
              Back to Dashboard
            </button>
          </div>
        );
      default:
        return (
          <StudentDashboardHome
            studentName={studentName}
            targetDomains={targetDomains}
            assessmentPassed={assessmentPassed}
            lastAttempt={lastAttempt}
            hasRecommendationForCurrentDomains={hasRecommendationForCurrentDomains}
            attemptCount={attemptCountToday}
            attemptCountLabel="used today"
            maxAttemptsPerDay={2}
            tasksCompleted={tasksCompleted}
            onStartAssessment={handleStartAssessment}
            assessmentError={assessmentError}
          />
        );
    }
  };

  return (
    <div className="dashboard-container student-dashboard">
      {/* Top Navbar */}
      <nav className="dashboard-nav">
        <div className="student-dashboard-nav">
          <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ width: 42, height: 42, borderRadius: 10, background: 'linear-gradient(135deg, #0f766e 0%, #0d9488 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', boxShadow: '0 2px 8px rgba(15, 118, 110, 0.3)' }}>
                <GraduationCapIcon className="w-6 h-6" />
              </div>
              <div className="hidden sm:block">
                <div className="text-lg font-semibold text-gray-900">Virtual Internship Hub</div>
                <div className="text-xs text-gray-500">Student Portal</div>
              </div>
            </div>
            <div className="nav-links hidden md:flex">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive = activeView === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveView(item.id)}
                    className={isActive ? 'active' : ''}
                  >
                    <Icon className="w-4 h-4" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button type="button" className="nav-icon-btn relative" onClick={() => setShowNotifications(!showNotifications)} aria-label="Notifications">
              <BellIcon className="w-5 h-5" />
              <span className="absolute top-0 right-0 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">0</span>
            </button>
            <div className="nav-actions" style={{ gap: '0.75rem' }}>
              <div className="hidden sm:block text-right">
                <div className="nav-user-name">{studentName}</div>
                <div className="nav-user-meta">
                  {lastAttempt?.recommended_domains?.[0] ? (
                    <>Recommended: <strong>{lastAttempt.recommended_domains[0].name}</strong></>
                  ) : (
                    'Student'
                  )}
                </div>
              </div>
              <button type="button" onClick={() => setActiveView('profile')} className="nav-icon-btn" title="Profile">
                <UserIcon className="w-5 h-5" />
              </button>
              <button type="button" onClick={handleLogout} className="nav-icon-btn" title="Logout">
                <LogOutIcon className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <div
        className={`dashboard-content ${['intro', 'test', 'result'].includes(assessmentView) ? 'assessment-active' : ''}`}
      >
        {renderContent()}
      </div>

      {/* Career Chatbot trigger – hidden during assessment */}
      {!['intro', 'test', 'result'].includes(assessmentView) && (
        <button type="button" className="chatbot-trigger" onClick={() => setShowChatbot(true)} title="Career Guidance">
          <MessageCircleIcon className="w-6 h-6" />
        </button>
      )}

      {/* Career Chatbot panel */}
      {showChatbot && <CareerChatbotPanel onClose={() => setShowChatbot(false)} />}
    </div>
  );
}

function StudentDashboardHome({ studentName, targetDomains, assessmentPassed, lastAttempt, hasRecommendationForCurrentDomains = false, attemptCount, attemptCountLabel = 'used', maxAttemptsPerDay = 2, tasksCompleted = 0, onStartAssessment, assessmentError }) {
  const recommendedDomain = lastAttempt?.recommended_domains?.[0];
  const previousRecommendation = !hasRecommendationForCurrentDomains && lastAttempt?.recommended_domains?.[0];

  return (
    <div className="dashboard-section">
      {/* Welcome card – separate target domains (chosen) vs recommended domain (from assessment) */}
      <div className="welcome-card">
        <h2>Welcome back, {studentName}!</h2>
        <p>
          {hasRecommendationForCurrentDomains
            ? 'Great job on passing your assessment. Check out your recommended tasks below.'
            : assessmentPassed
              ? 'Take the assessment again for your current target domains to get a new recommendation.'
              : 'Complete your skill assessment to unlock personalized tasks and get a domain recommendation.'}
        </p>
        {targetDomains.length > 0 && targetDomains[0] !== 'Your domains' && (
          <div style={{ marginTop: '0.75rem' }}>
            <span style={{ fontSize: '0.8125rem', color: 'rgba(255,255,255,0.85)', marginRight: '0.5rem' }}>Your target domains:</span>
            <div className="domain-tags" style={{ marginTop: '0.25rem' }}>
              {targetDomains.map((d, i) => (
                <span key={i}>{d}</span>
              ))}
            </div>
          </div>
        )}
        {hasRecommendationForCurrentDomains && recommendedDomain && (
          <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.3)' }}>
            <span style={{ fontSize: '0.8125rem', color: 'rgba(255,255,255,0.85)', marginRight: '0.5rem' }}>Your recommended domain:</span>
            <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{recommendedDomain.name}</span>
          </div>
        )}
        {previousRecommendation && (
          <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.3)' }}>
            <span style={{ fontSize: '0.8125rem', color: 'rgba(255,255,255,0.85)' }}>Previous recommendation (before you changed domains): </span>
            <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{previousRecommendation.name}</span>
          </div>
        )}
      </div>

      {assessmentError && (
        <div className="assessment-error-card">
          <p>{assessmentError}</p>
        </div>
      )}

      {/* Assessment block – Start Assessment when no recommendation for current domains; Assessment Passed when we have one */}
      {targetDomains.length < 2 ? (
        <div className="assessment-cta-block">
          <div className="assessment-cta-inner">
            <div className="assessment-cta-icon select">
              <TargetIcon className="w-8 h-8" />
            </div>
            <div style={{ flex: 1 }}>
              <h2>Select your domains of interest</h2>
              <p style={{ color: '#475569', marginBottom: '1rem', fontSize: '0.9375rem', lineHeight: 1.5 }}>
                Choose 2 to 3 domains you want to focus on. Then you can take the skill assessment to get a recommended domain.
              </p>
              <p style={{ fontSize: '0.875rem', color: '#64748b', margin: 0 }}>
                Go to your profile to select or update your target domains.
              </p>
            </div>
          </div>
        </div>
      ) : hasRecommendationForCurrentDomains ? (
        <div className="assessment-passed-block">
          <div className="passed-inner">
            <div className="passed-icon">
              <CheckCircleIcon className="w-6 h-6" />
            </div>
            <div style={{ flex: 1 }}>
              <h3>Assessment Passed!</h3>
              <p>
                Your recommended domain <strong>{recommendedDomain.name}</strong> is set. We&apos;ve unlocked beginner-level tasks for you.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="assessment-cta-block">
          <div className="assessment-cta-inner">
            <div className="assessment-cta-icon alert">
              <AlertCircleIcon className="w-8 h-8" />
            </div>
            <div style={{ flex: 1 }}>
              <h2>Start Assessment</h2>
              <p style={{ color: '#475569', marginBottom: '1rem', fontSize: '0.9375rem', lineHeight: 1.5 }}>
                {assessmentPassed
                  ? 'Take the assessment again for your current target domains to get a new recommendation.'
                  : `Take the skill assessment for: ${targetDomains.join(', ')}. Get an AI-based domain recommendation.`}
              </p>
              <div className="assessment-card-inner">
                <button type="button" className="btn-start-assessment" onClick={onStartAssessment}>
                  Start Assessment
                </button>
              </div>
              <p className="attempts-meta">{attemptCount} of {maxAttemptsPerDay} attempt(s) {attemptCountLabel}</p>
            </div>
          </div>
        </div>
      )}

      {/* Tasks – unlocked only when we have a recommendation for current target domains */}
      {hasRecommendationForCurrentDomains ? (
        <div className="tasks-section-card">
          <div className="tasks-section-header">
            <div>
              <h2 style={{ marginBottom: '0.35rem', color: '#0f172a', fontSize: '1.25rem', fontWeight: 600 }}>Tasks unlocked</h2>
              <p style={{ color: '#64748b', fontSize: '0.875rem', margin: 0 }}>Your tasks are unlocked. Go to My Tasks to see your recommended tasks.</p>
            </div>
            <span className="task-badge beginner">Unlocked</span>
          </div>
          <div style={{ padding: '1rem 1.5rem', textAlign: 'center' }}>
            <p style={{ color: '#0f766e', fontWeight: 500, margin: 0 }}>Your tasks are unlocked.</p>
          </div>
        </div>
      ) : (
        <div className="tasks-locked-block">
          <div className="lock-icon-wrap">
            <LockIcon className="w-6 h-6" />
          </div>
          <h3 style={{ marginBottom: '0.5rem', color: '#0f172a', fontWeight: 600 }}>Tasks Locked</h3>
          <p style={{ color: '#64748b', marginBottom: '1rem', maxWidth: 400, marginLeft: 'auto', marginRight: 'auto', fontSize: '0.9375rem' }}>
            Complete the skill assessment above to unlock personalized tasks based on your domains and performance.
          </p>
          <button type="button" onClick={targetDomains.length >= 2 ? onStartAssessment : undefined} className="btn-outline-primary" disabled={targetDomains.length < 2}>Take Assessment Now</button>
        </div>
      )}

      {/* Progress summary */}
      <div className="progress-cards-grid">
        <div className="progress-card">
          <div className="progress-icon" style={{ background: '#ccfbf1', color: '#0f766e' }}><TargetIcon className="w-6 h-6" /></div>
          <div>
            <div className="progress-value">{tasksCompleted}</div>
            <div className="progress-label">Tasks Completed</div>
          </div>
        </div>
        <div className="progress-card">
          <div className="progress-icon" style={{ background: '#f5f3ff', color: '#7c3aed' }}><AwardIcon className="w-6 h-6" /></div>
          <div>
            <div className="progress-value">{assessmentPassed ? 'Intermediate' : 'Not assessed'}</div>
            <div className="progress-label">Skill Level</div>
          </div>
        </div>
        <div className="progress-card">
          <div className="progress-icon" style={{ background: assessmentPassed ? '#ecfdf5' : '#f1f5f9', color: assessmentPassed ? '#059669' : '#9ca3af' }}><CheckCircleIcon className="w-6 h-6" /></div>
          <div>
            <div className="progress-value">{assessmentPassed ? 'Passed' : `${attemptCount}/2`}</div>
            <div className="progress-label">Skill Assessment</div>
          </div>
        </div>
      </div>

      {/* Quick links */}
      <div className="quick-links-card">
        <h3>Quick Links</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
          <button type="button" className="quick-link-btn">
            <div className="quick-link-icon"><FolderOpenIcon className="w-5 h-5" /></div>
            <div>
              <div className="quick-link-title">View Portfolio</div>
              <div className="quick-link-desc">Showcase your work</div>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}

function StudentTasksPlaceholder({ assessmentPassed, onStartAssessment }) {
  if (!assessmentPassed) {
    return (
      <div className="dashboard-section">
        <h1>My Tasks</h1>
        <p className="section-desc">Complete the skill assessment first to see recommended tasks.</p>
        <div className="tasks-locked-block">
          <div className="lock-icon-wrap"><LockIcon className="w-6 h-6" /></div>
          <p style={{ color: '#6b7280', marginBottom: '1rem' }}>Tasks are recommended after you pass the assessment.</p>
          <button type="button" onClick={onStartAssessment} style={{ padding: '0.5rem 1rem', background: '#2563eb', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer' }}>Go to Assessment</button>
        </div>
      </div>
    );
  }
  return (
    <div className="dashboard-section">
      <h1>My Tasks</h1>
      <p className="section-desc">Your assigned and recommended tasks (beginner first).</p>
      <div className="info-card">
        <p>Task list will load from API. Beginner tasks shown first based on your assessment score.</p>
      </div>
    </div>
  );
}

function StudentPortfolioPlaceholder() {
  return (
    <div className="dashboard-section">
      <h1>My Portfolio</h1>
      <p className="section-desc">Showcase completed projects (FR6).</p>
      <div className="info-card">
        <p>Portfolio items from completed projects will appear here. Connect API when ready.</p>
      </div>
    </div>
  );
}

function CareerChatbotPanel({ onClose }) {
  const [messages, setMessages] = useState([
    { id: 1, type: 'bot', text: "Hi! I'm your career guidance assistant. I can help with freelancing tips, career advice, and skill development. What would you like to know?", time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) },
  ]);
  const [inputValue, setInputValue] = useState('');

  const send = (text) => {
    if (!text.trim()) return;
    const userMsg = { id: messages.length + 1, type: 'user', text: text.trim(), time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setTimeout(() => {
      const botText = getBotReply(text);
      setMessages((prev) => [...prev, { id: prev.length + 2, type: 'bot', text: botText, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }]);
    }, 600);
  };

  return (
    <>
      <div className="chatbot-overlay" onClick={onClose} aria-hidden />
      <div className="chatbot-panel">
        <div className="chatbot-header">
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Career Guidance & Freelancing Tips</h3>
          <button type="button" onClick={onClose} style={{ padding: '0.25rem', background: 'transparent', border: 'none', cursor: 'pointer' }} aria-label="Close"><XIcon className="w-5 h-5" /></button>
        </div>
        <div className="chat-messages">
          {messages.map((m) => (
            <div key={m.id} className={`chat-message ${m.type}`}>
              <div>{m.text}</div>
              <div style={{ fontSize: '0.7rem', opacity: 0.8, marginTop: '0.25rem' }}>{m.time}</div>
            </div>
          ))}
        </div>
        <div style={{ padding: '0.5rem', borderTop: '1px solid #e5e7eb' }}>
          {CHATBOT_SUGGESTIONS.map((q, i) => (
            <button key={i} type="button" onClick={() => send(q)} style={{ display: 'block', width: '100%', marginBottom: '0.35rem', padding: '0.4rem 0.75rem', background: '#f3f4f6', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.8rem', textAlign: 'left' }}>{q}</button>
          ))}
        </div>
        <div className="chat-input-wrap">
          <input type="text" value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send(inputValue)} placeholder="Ask about careers or freelancing..." />
          <button type="button" onClick={() => send(inputValue)}><SendIcon className="w-4 h-4" /></button>
        </div>
      </div>
    </>
  );
}

function XIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

export default StudentDashboard;
