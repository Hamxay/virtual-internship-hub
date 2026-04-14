import React, { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getSessions, getSessionMessages, sendMessage } from '../../api/chat.api';
import { MessageCircleIcon, SendIcon } from '../ui/Icons';
import './CareerCoachWidget.css';

const ACTION_CHIPS = [
  {
    label: 'Draft Upwork Pitch',
    text:
      'Help me draft an Upwork proposal pitch based on my completed internship projects and domain focus. Use markdown with clear sections I can paste and edit.',
  },
  {
    label: 'Resume Review',
    text:
      'How should I describe my completed Virtual Internship Hub projects on my resume? Give impact-focused bullet patterns and what to avoid—no full resume text.',
  },
];

function HistorySessionsIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
      />
    </svg>
  );
}

function CloseIcon({ className = 'w-5 h-5' }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
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
    return new Date(iso).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
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

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, []);

  useEffect(() => {
    if (!open) return;
    scrollToBottom();
  }, [open, messages, awaiting, historyMode, scrollToBottom]);

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
        <button type="button" className="ccw-fab" onClick={() => setOpen(true)} title="Career Coach" aria-label="Open Career Coach">
          <MessageCircleIcon className="w-6 h-6" />
        </button>
      )}

      {open && (
        <>
          <button type="button" className="ccw-overlay" onClick={() => setOpen(false)} aria-label="Close overlay" />
          <div className="ccw-panel" role="dialog" aria-labelledby="ccw-title">
            <header className="ccw-header">
              <h2 id="ccw-title">Career Coach</h2>
              <div className="ccw-header-actions">
                <button
                  type="button"
                  className="ccw-icon-btn"
                  onClick={() => setHistoryMode((v) => !v)}
                  aria-pressed={historyMode}
                  title={historyMode ? 'Back to chat' : 'Conversation history'}
                  aria-label={historyMode ? 'Back to chat' : 'Conversation history'}
                >
                  <HistorySessionsIcon className="w-5 h-5" />
                </button>
                <button type="button" className="ccw-icon-btn" onClick={() => setOpen(false)} title="Close" aria-label="Close Career Coach">
                  <CloseIcon className="w-5 h-5" />
                </button>
              </div>
            </header>

            <div className="ccw-body">
              {historyMode ? (
                <div className="ccw-history">
                  {sessionsLoading && <p className="ccw-empty">Loading…</p>}
                  {!sessionsLoading && sessions.length === 0 && <p className="ccw-empty">No past conversations yet. Send a message to start one.</p>}
                  {!sessionsLoading &&
                    sessions.map((s) => (
                      <button key={s.id} type="button" className="ccw-history-item" onClick={() => loadSession(s.id)}>
                        <div>Session #{s.id}</div>
                        <div className="ccw-history-meta">{formatSessionWhen(s.created_at)}</div>
                      </button>
                    ))}
                </div>
              ) : (
                <div className="ccw-messages">
                  {messages.length === 0 && !awaiting && (
                    <p className="ccw-empty">Ask about internships, freelancing, or your career path. Your coach uses your profile and project progress for context.</p>
                  )}
                  {messages.map((m) => (
                    <div key={m.id} className={`ccw-bubble ${m.role === 'user' ? 'ccw-bubble-user' : 'ccw-bubble-model'}`}>
                      {m.role === 'model' ? (
                        <div className="ccw-md">
                          <ReactMarkdown>{m.content || ''}</ReactMarkdown>
                        </div>
                      ) : (
                        <div>{m.content}</div>
                      )}
                      <div className="ccw-bubble-time">{formatTime(m.timestamp)}</div>
                    </div>
                  ))}
                  {awaiting && (
                    <div className="ccw-typing" aria-live="polite">
                      …
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
                  <button key={c.label} type="button" className="ccw-chip" onClick={() => handleSend(c.text)} disabled={awaiting}>
                    {c.label}
                  </button>
                ))}
              </div>
            )}

            {!historyMode && (
              <form className="ccw-input-row" onSubmit={onSubmit}>
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Message your coach…"
                  disabled={awaiting}
                  autoComplete="off"
                />
                <button type="submit" disabled={awaiting || !input.trim()} aria-label="Send">
                  <SendIcon className="w-4 h-4" />
                </button>
              </form>
            )}
          </div>
        </>
      )}
    </>
  );
}
