import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { mentorStudentChatApi } from '../../api/mentorStudentChat.api';

function formatDateTime(value) {
  if (!value) return '';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '';
  return dt.toLocaleString();
}

export default function MentorStudentChatTab({ role = 'student' }) {
  const CONVERSATION_POLL_MS = 3000;
  const MESSAGE_POLL_MS = 2000;
  const isStudent = role === 'student';
  const mentorMode = !isStudent;
  const [conversations, setConversations] = useState([]);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [eligibleMentors, setEligibleMentors] = useState([]);
  const [eligibleStudents, setEligibleStudents] = useState([]);
  const [mentorIdToStart, setMentorIdToStart] = useState('');
  const [studentIdToStart, setStudentIdToStart] = useState('');
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [startingConversation, setStartingConversation] = useState(false);
  const [sending, setSending] = useState(false);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');

  const loadConversations = useCallback(async () => {
    try {
      const { data } = await mentorStudentChatApi.getConversations();
      const rows = Array.isArray(data) ? data : [];
      setConversations(rows);
      if (!selectedConversationId && rows.length > 0) {
        setSelectedConversationId(rows[0].id);
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to load conversations.');
    } finally {
      setLoadingConversations(false);
    }
  }, [selectedConversationId]);

  const loadMessages = useCallback(async (conversationId, { silent = false } = {}) => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    if (!silent) setLoadingMessages(true);
    try {
      const { data } = await mentorStudentChatApi.getMessages(conversationId);
      setMessages(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to load messages.');
    } finally {
      if (!silent) setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (!isStudent) return;
    mentorStudentChatApi.getEligibleMentors()
      .then((res) => {
        const rows = Array.isArray(res?.data) ? res.data : [];
        setEligibleMentors(rows);
        if (rows.length > 0) setMentorIdToStart(String(rows[0].mentor_id));
      })
      .catch(() => {});
  }, [isStudent]);

  useEffect(() => {
    if (isStudent) return;
    mentorStudentChatApi.getEligibleStudents()
      .then((res) => {
        const rows = Array.isArray(res?.data) ? res.data : [];
        setEligibleStudents(rows);
        if (rows.length > 0) setStudentIdToStart(String(rows[0].student_id));
      })
      .catch(() => {});
  }, [isStudent]);

  useEffect(() => {
    loadMessages(selectedConversationId, { silent: false });
  }, [selectedConversationId, loadMessages]);

  useEffect(() => {
    const timer = setInterval(() => {
      loadConversations();
    }, CONVERSATION_POLL_MS);
    return () => clearInterval(timer);
  }, [loadConversations]);

  useEffect(() => {
    if (!selectedConversationId) return undefined;
    const timer = setInterval(() => {
      loadMessages(selectedConversationId, { silent: true });
    }, MESSAGE_POLL_MS);
    return () => clearInterval(timer);
  }, [loadMessages, selectedConversationId]);

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.id === selectedConversationId) || null,
    [conversations, selectedConversationId],
  );

  const handleStartConversation = async () => {
    const startPayload = isStudent
      ? { mentor_id: Number(mentorIdToStart) }
      : { student_id: Number(studentIdToStart) };
    if (isStudent ? !mentorIdToStart : !studentIdToStart) return;
    setStartingConversation(true);
    setError('');
    try {
      const { data } = await mentorStudentChatApi.startConversation(startPayload);
      await loadConversations();
      setSelectedConversationId(data?.id || null);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Could not start chat.');
    } finally {
      setStartingConversation(false);
    }
  };

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || !selectedConversationId) return;
    setSending(true);
    setError('');
    try {
      await mentorStudentChatApi.sendMessage(selectedConversationId, text);
      setDraft('');
      await loadMessages(selectedConversationId);
      await loadConversations();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Could not send message.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      className="dashboard-section"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        background: mentorMode ? 'linear-gradient(180deg, #f0f9ff 0%, #eef2ff 100%)' : undefined,
        border: mentorMode ? '1px solid #bfdbfe' : undefined,
        borderRadius: mentorMode ? 14 : undefined,
        padding: mentorMode ? '0.75rem' : undefined,
      }}
    >
      <div>
        <h1>{isStudent ? 'Mentor Chat' : 'Student Chats'}</h1>
        <p className="section-desc">
          {isStudent
            ? 'Choose a mentor from your target domains and start a general chat.'
            : 'Choose a student from your expertise domain and start a general chat.'}
        </p>
      </div>

      {isStudent && (
        <div
          className="info-card info-card--plain"
          style={{
            display: 'flex',
            gap: '0.75rem',
            alignItems: 'center',
            background: '#f8fafc',
            border: '1px solid #cbd5e1',
            borderRadius: 12,
          }}
        >
          <select
            value={mentorIdToStart}
            onChange={(e) => setMentorIdToStart(e.target.value)}
            style={{ flex: 1, minWidth: 220 }}
          >
            <option value="">Select mentor</option>
            {eligibleMentors.map((mentor) => (
              <option key={mentor.mentor_id} value={mentor.mentor_id}>
                {mentor.username}
                {mentor.expertise_domain_name ? ` (${mentor.expertise_domain_name})` : ''}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-primary-green"
            onClick={handleStartConversation}
            disabled={startingConversation || !mentorIdToStart}
          >
            {startingConversation ? 'Opening...' : 'Start chat'}
          </button>
        </div>
      )}

      {mentorMode && (
        <div
          className="info-card info-card--plain"
          style={{
            display: 'flex',
            gap: '0.75rem',
            alignItems: 'center',
            background: '#f8fafc',
            border: '1px solid #cbd5e1',
            borderRadius: 12,
          }}
        >
          <select
            value={studentIdToStart}
            onChange={(e) => setStudentIdToStart(e.target.value)}
            style={{ flex: 1, minWidth: 220 }}
          >
            <option value="">Select student</option>
            {eligibleStudents.map((student) => (
              <option key={student.student_id} value={student.student_id}>
                {student.username}
                {student.domain_names?.length ? ` (${student.domain_names.join(', ')})` : ''}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-primary-green"
            onClick={handleStartConversation}
            disabled={startingConversation || !studentIdToStart}
          >
            {startingConversation ? 'Opening...' : 'Start chat'}
          </button>
        </div>
      )}

      {error ? <p className="student-tasks-error">{error}</p> : null}

      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'minmax(220px, 320px) minmax(0, 1fr)' }}>
        <aside
          className="info-card info-card--plain"
          style={{
            maxHeight: 520,
            overflowY: 'auto',
            background: mentorMode ? '#eef2ff' : '#f8fafc',
            border: mentorMode ? '1px solid #c7d2fe' : '1px solid #dbeafe',
            borderRadius: 12,
          }}
        >
          <h3 style={{ marginTop: 0, marginBottom: '0.75rem', color: '#0f172a' }}>Conversations</h3>
          {loadingConversations ? (
            <p className="student-task-muted">Loading...</p>
          ) : conversations.length === 0 ? (
            <p className="student-task-muted">No conversations yet.</p>
          ) : (
            conversations.map((conv) => {
              const counterpart = isStudent ? conv.mentor_name : conv.student_name;
              const selected = selectedConversationId === conv.id;
              return (
                <button
                  key={conv.id}
                  type="button"
                  onClick={() => setSelectedConversationId(conv.id)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    marginBottom: '0.5rem',
                    border: selected ? '1px solid #14b8a6' : (mentorMode ? '1px solid #c7d2fe' : '1px solid #dbeafe'),
                    background: selected ? '#ccfbf1' : '#ffffff',
                    borderRadius: 8,
                    padding: '0.6rem 0.7rem',
                    cursor: 'pointer',
                    boxShadow: selected ? '0 1px 8px rgba(20, 184, 166, 0.12)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
                    <strong style={{ fontSize: '0.9rem', color: '#0f172a' }}>{counterpart}</strong>
                    {conv.unread_count > 0 ? (
                      <span className="task-badge beginner">{conv.unread_count}</span>
                    ) : null}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#334155', marginTop: '0.25rem' }}>
                    {conv.domain_name || conv.mentor_domain_name || 'General chat'}
                  </div>
                  {conv.last_message ? (
                    <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.2rem' }}>{conv.last_message}</div>
                  ) : null}
                </button>
              );
            })
          )}
        </aside>

        <section
          className="info-card info-card--plain"
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: 520,
            minHeight: 520,
            overflow: 'hidden',
            background: mentorMode ? '#e0e7ff' : '#f0f9ff',
            border: mentorMode ? '1px solid #c7d2fe' : '1px solid #bfdbfe',
            borderRadius: 12,
          }}
        >
          {selectedConversation ? (
            <>
              <div
                style={{
                  borderBottom: mentorMode ? '1px solid #c7d2fe' : '1px solid #bfdbfe',
                  paddingBottom: '0.65rem',
                  marginBottom: '0.75rem',
                }}
              >
                <strong style={{ color: '#0f172a' }}>
                  {isStudent ? selectedConversation.mentor_name : selectedConversation.student_name}
                </strong>
                <p style={{ margin: '0.25rem 0 0 0', color: '#64748b', fontSize: '0.85rem' }}>
                  {selectedConversation.domain_name || selectedConversation.mentor_domain_name || 'General chat'}
                </p>
              </div>

              <div
                style={{
                  flex: 1,
                  minHeight: 0,
                  overflowY: 'auto',
                  paddingRight: '0.25rem',
                  background: '#ffffff',
                  border: mentorMode ? '1px solid #c7d2fe' : '1px solid #dbeafe',
                  borderRadius: 10,
                  padding: '0.75rem',
                }}
              >
                {loadingMessages ? (
                  <p className="student-task-muted">Loading messages...</p>
                ) : messages.length === 0 ? (
                  <p className="student-task-muted">No messages yet. Start the conversation.</p>
                ) : (
                  messages.map((msg) => {
                    const isMine = (isStudent && msg.sender_role === 'STUDENT')
                      || (!isStudent && msg.sender_role === 'MENTOR');
                    return (
                      <div
                        key={msg.id}
                        style={{
                          display: 'flex',
                          justifyContent: isMine ? 'flex-end' : 'flex-start',
                          marginBottom: '0.5rem',
                        }}
                      >
                        <div
                          style={{
                            maxWidth: '78%',
                            borderRadius: 10,
                            padding: '0.55rem 0.7rem',
                            background: isMine ? '#0d9488' : (mentorMode ? '#eef2ff' : '#eff6ff'),
                            color: isMine ? '#fff' : '#0f172a',
                            border: isMine ? 'none' : (mentorMode ? '1px solid #c7d2fe' : '1px solid #bfdbfe'),
                          }}
                        >
                          <div style={{ fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                          <div style={{ marginTop: '0.2rem', fontSize: '0.7rem', opacity: 0.85 }}>
                            {formatDateTime(msg.created_at)}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div
                style={{
                  display: 'flex',
                  gap: '0.5rem',
                  marginTop: '0.75rem',
                  flexShrink: 0,
                  background: '#ffffff',
                  border: mentorMode ? '1px solid #c7d2fe' : '1px solid #dbeafe',
                  borderRadius: 10,
                  padding: '0.5rem',
                }}
              >
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Write a message..."
                  rows={2}
                  style={{
                    flex: 1,
                    border: '1px solid #cbd5e1',
                    borderRadius: 10,
                    padding: '0.65rem 0.75rem',
                    fontSize: '0.9rem',
                    color: '#0f172a',
                    outline: 'none',
                    resize: 'none',
                    background: '#fff',
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={sending || !draft.trim()}
                  style={{
                    minWidth: 88,
                    border: 'none',
                    borderRadius: 10,
                    padding: '0.55rem 0.9rem',
                    background: sending || !draft.trim() ? '#94a3b8' : '#0d9488',
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: '0.875rem',
                    cursor: sending || !draft.trim() ? 'not-allowed' : 'pointer',
                    alignSelf: 'flex-end',
                  }}
                >
                  {sending ? 'Sending...' : 'Send'}
                </button>
              </div>
            </>
          ) : (
            <p className="student-task-muted">Select a conversation to view messages.</p>
          )}
        </section>
      </div>
    </div>
  );
}
