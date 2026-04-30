import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getSessions, getSessionMessages, sendMessage } from '../../api/chat.api';
import { MessageCircleIcon, SendIcon } from '../ui/Icons';
import './CareerCoachWidget.css';

const ACTION_CHIPS = [
  {
    label: 'Draft Upwork Pitch',
    text: 'Help me draft an Upwork proposal pitch based on my completed internship projects and domain focus. Use markdown with clear sections I can paste and edit.',
  },
  {
    label: 'Resume Bullet Tips',
    text: 'How should I describe my completed Virtual Internship Hub projects on my resume? Give impact-focused bullet patterns and what to avoid—no full resume text.',
  },
  {
    label: 'Freelance Pricing',
    text: 'How should I price my first freelance project given my current skill level and the domains I have worked in? Give a practical range and negotiation tips.',
  },
];

function CloseIcon() {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function CoachAvatarIcon() {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75}
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  );
}

function WelcomeIcon() {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75}
        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
    </svg>
  );
}

function formatTime(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function formatSessionWhen(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

/**
 * @param {{ hidden?: boolean, hasCompletedProjects?: boolean }} props
 */
export default function CareerCoachWidget({ hidden = false, hasCompletedProjects = false }) {
  const [open, setOpen] = useState(false);
  const [historyMode, setHistoryMode] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [awaiting, setAwaiting] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, []);

  useEffect(() => {
    if (!open) return;
    scrollToBottom();
  }, [open, messages, awaiting, historyMode, scrollToBottom]);

  useEffect(() => {
    if (open && !historyMode && !awaiting) {
      inputRef.current?.focus();
    }
  }, [open, historyMode, awaiting]);

  useEffect(() => {
    if (!open || !historyMode) return;
    setSessionsLoading(true);
    setError(null);
    getSessions()
      .then(setSessions)
      .catch((err) => {
        setError(err.response?.data?.detail || err.message || 'Could not load sessions.');
        setSessions([]);
      })
      .finally(() => setSessionsLoading(false));
  }, [open, historyMode]);

  const loadSession = async (id) => {
    setError(null);
    setSessionsLoading(true);
    try {
      const list = await getSessionMessages(id);
      setMessages(Array.isArray(list) ? list : []);
      setSessionId(id);
      setHistoryMode(false);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Could not load messages.');
    } finally {
      setSessionsLoading(false);
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setSessionId(null);
    setError(null);
    setHistoryMode(false);
  };

  const handleSend = async (rawText) => {
    const text = (rawText || '').trim();
    if (!text || awaiting) return;
    setError(null);
    setInput('');
    const optimistic = { id: `local-${Date.now()}`, role: 'user', content: text, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, optimistic]);
    setAwaiting(true);
    try {
      const data = await sendMessage(text, sessionId);
      setSessionId(data.session_id);
      setMessages((prev) => {
        const rest = prev.filter((m) => m.id !== optimistic.id);
        const next = [...rest];
        if (data.user_message) next.push(data.user_message);
        if (data.assistant_message) next.push(data.assistant_message);
        return next;
      });
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setError(err.response?.data?.detail || err.message || 'Message could not be sent.');
    } finally {
      setAwaiting(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    handleSend(input);
  };

  if (hidden) return null;

  return (
    <>
      {!open && (
        <button
          type="button"
          className="ccw-fab"
          onClick={() => setOpen(true)}
          title="Career Coach"
          aria-label="Open Career Coach"
        >
          <MessageCircleIcon />
        </button>
      )}

      {open && (
        <>
          <button
            type="button"
            className="ccw-overlay"
            onClick={() => setOpen(false)}
            aria-label="Close Career Coach"
          />
          <div className="ccw-panel" role="dialog" aria-labelledby="ccw-title">

            <header className="ccw-header">
              <div className="ccw-header-left">
                <div className="ccw-header-avatar">
                  <CoachAvatarIcon />
                </div>
                <div className="ccw-header-text">
                  <h2 id="ccw-title">Career Coach</h2>
                  <p>AI-powered guidance</p>
                </div>
              </div>
              <div className="ccw-header-actions">
                <button
                  type="button"
                  className="ccw-icon-btn"
                  onClick={() => setHistoryMode((v) => !v)}
                  aria-pressed={historyMode}
                  title={historyMode ? 'Back to chat' : 'Conversation history'}
                  aria-label={historyMode ? 'Back to chat' : 'Conversation history'}
                >
                  <HistoryIcon />
                </button>
                <button
                  type="button"
                  className="ccw-icon-btn"
                  onClick={() => setOpen(false)}
                  title="Close"
                  aria-label="Close Career Coach"
                >
                  <CloseIcon />
                </button>
              </div>
            </header>

            <div className="ccw-body">
              {historyMode ? (
                <div className="ccw-history">
                  <div className="ccw-history-header">
                    <span className="ccw-history-header-label">Past conversations</span>
                    <button type="button" className="ccw-new-chat-btn" onClick={startNewChat}>
                      + New chat
                    </button>
                  </div>
                  <div className="ccw-history-list">
                    {sessionsLoading && <p className="ccw-empty">Loading…</p>}
                    {!sessionsLoading && sessions.length === 0 && (
                      <p className="ccw-empty">No past conversations yet. Send a message to start one.</p>
                    )}
                    {!sessionsLoading && sessions.map((s) => (
                      <button key={s.id} type="button" className="ccw-history-item" onClick={() => loadSession(s.id)}>
                        <div className="ccw-history-item__title">
                          {s.preview || `Session #${s.id}`}
                        </div>
                        <div className="ccw-history-meta">{formatSessionWhen(s.created_at)}</div>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="ccw-messages">
                  {messages.length === 0 && !awaiting ? (
                    <div className="ccw-welcome">
                      <div className="ccw-welcome-icon">
                        <WelcomeIcon />
                      </div>
                      <p className="ccw-welcome-title">Your Career Coach</p>
                      <p className="ccw-welcome-sub">
                        Ask about internships, freelancing, resume tips, or your career path.
                        I use your project progress and domain focus for context.
                      </p>
                    </div>
                  ) : (
                    <>
                      {messages.map((m) => (
                        <div
                          key={m.id}
                          className={`ccw-bubble ${m.role === 'user' ? 'ccw-bubble-user' : 'ccw-bubble-model'}`}
                        >
                          {m.role === 'model' ? (
                            <div className="ccw-md">
                              <ReactMarkdown>{m.content || ''}</ReactMarkdown>
                            </div>
                          ) : (
                            <div>{m.content}</div>
                          )}
                          {m.timestamp ? (
                            <div className="ccw-bubble-time">{formatTime(m.timestamp)}</div>
                          ) : null}
                        </div>
                      ))}
                    </>
                  )}
                  {awaiting && (
                    <div className="ccw-typing" aria-live="polite" aria-label="Coach is typing">
                      <span className="ccw-typing-dot" />
                      <span className="ccw-typing-dot" />
                      <span className="ccw-typing-dot" />
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>

            {error && <div className="ccw-error">{error}</div>}

            {!historyMode && hasCompletedProjects && (
              <div className="ccw-chips">
                {ACTION_CHIPS.map((c) => (
                  <button
                    key={c.label}
                    type="button"
                    className="ccw-chip"
                    onClick={() => handleSend(c.text)}
                    disabled={awaiting}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            )}

            {!historyMode && (
              <form className="ccw-input-row" onSubmit={onSubmit}>
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Message your coach…"
                  disabled={awaiting}
                  autoComplete="off"
                />
                <button type="submit" disabled={awaiting || !input.trim()} aria-label="Send message">
                  <SendIcon />
                </button>
              </form>
            )}
          </div>
        </>
      )}
    </>
  );
}
