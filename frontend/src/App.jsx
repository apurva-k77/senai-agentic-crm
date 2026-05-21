import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate, useParams } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar,
} from 'recharts'

const API = ''
const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

async function api(path, opts = {}) {
  const r = await fetch(API + path, opts)
  const j = await r.json()
  if (!r.ok) throw new Error(j.message || r.statusText)
  return j
}

function sentimentBadge(score) {
  if (score == null) return <span className="badge neu">—</span>
  if (score < -0.3) return <span className="badge neg">{score.toFixed(2)}</span>
  if (score > 0.3) return <span className="badge pos">{score.toFixed(2)}</span>
  return <span className="badge neu">{score.toFixed(2)}</span>
}

function urgencyBadge(u) {
  if (!u) return null
  const c = u === 'Critical' ? 'crit' : u === 'High' ? 'high' : 'neu'
  return <span className={`badge ${c}`}>{u}</span>
}

function highlightEntities(text, entities) {
  if (!text || !entities) return text
  let out = text
  const all = [
    ...(entities.monetary_amounts || []),
    ...(entities.order_ids || []).map((id) => `#${id}`),
    ...(entities.ticket_ids || []),
  ]
  all.forEach((e) => {
    if (e && out.includes(e)) out = out.replace(e, `<span class="entity">${e}</span>`)
  })
  return <span dangerouslySetInnerHTML={{ __html: out }} />
}

function Layout({ children }) {
  return (
    <div className="layout">
      <nav className="sidebar">
        <h2 style={{ marginTop: 0 }}>SenAI CRM</h2>
        <Link to="/">Mission Control</Link>
        <Link to="/analytics">Analytics</Link>
      </nav>
      <div className="main">{children}</div>
    </div>
  )
}

function Inbox() {
  const [tab, setTab] = useState('all')
  const [q, setQ] = useState('')
  const [emails, setEmails] = useState([])
  const [stats, setStats] = useState({})
  const [poll, setPoll] = useState(true)
  const nav = useNavigate()

  const load = useCallback(async () => {
    const tabMap = { all: 'all', human: 'human', auto: 'auto', escalated: 'escalated', spam: 'spam' }
    const [e, s] = await Promise.all([
      api(`/emails?tab=${tabMap[tab] || 'all'}&q=${encodeURIComponent(q)}`),
      api('/dashboard/stats'),
    ])
    setEmails(e.emails)
    setStats(s)
  }, [tab, q])

  useEffect(() => {
    load()
    if (!poll) return
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [load, poll])

  useEffect(() => {
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
    ws.onmessage = () => load()
    return () => ws.close()
  }, [load])

  const grouped = {}
  emails.forEach((em) => {
    const k = em.sender
    if (!grouped[k] || new Date(em.timestamp) > new Date(grouped[k].timestamp)) grouped[k] = em
  })
  const rows = Object.values(grouped)

  return (
    <Layout>
      <h1>Mission Control Inbox</h1>
      <div className="stats">
        {['pending', 'replied', 'escalated', 'critical', 'spam'].map((k) => (
          <div key={k} className="stat"><span>{k}</span><b>{stats[k] ?? 0}</b></div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', alignItems: 'center' }}>
        <input placeholder="Search subject/body…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 320 }} />
        <label><input type="checkbox" checked={poll} onChange={(e) => setPoll(e.target.checked)} /> Poll (5s)</label>
        <button className="primary" onClick={() => api('/api/stream/start?rate=2', { method: 'POST' }).then(load)}>Replay Stream</button>
      </div>
      <div className="tabs">
        {['all', 'human', 'auto', 'escalated', 'spam'].map((t) => (
          <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>
      <table>
        <thead>
          <tr><th>Sender</th><th>Subject</th><th>Sentiment</th><th>Category</th><th>Urgency</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map((em) => (
            <tr key={em.id} style={{ cursor: 'pointer' }} onClick={() => nav(`/thread/${encodeURIComponent(em.sender)}/${em.id}`)}>
              <td>{em.sender}</td>
              <td>{em.subject}</td>
              <td>{sentimentBadge(em.sentiment_score)}</td>
              <td>{em.category}</td>
              <td>{urgencyBadge(em.urgency)}</td>
              <td>{em.status}</td>
              <td onClick={(e) => e.stopPropagation()}>
                <button onClick={() => api(`/emails/${em.id}/bulk`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'spam' }) }).then(load)}>Spam</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Layout>
  )
}

function ThreadWorkspace() {
  const { contact, emailId } = useParams()
  const [threads, setThreads] = useState([])
  const [contactInfo, setContactInfo] = useState(null)
  const [dryRun, setDryRun] = useState(null)
  const [rag, setRag] = useState(null)
  const [reputation, setReputation] = useState(null)

  useEffect(() => {
    api(`/threads/${encodeURIComponent(contact)}`).then((d) => setThreads(d.threads))
    api(`/contacts/${encodeURIComponent(contact)}`).then(setContactInfo).catch(() => setContactInfo(null))
  }, [contact])

  const email = threads.flatMap((t) => t.emails).find((e) => String(e.id) === String(emailId))
  const thread = threads.find((t) => t.emails.some((e) => String(e.id) === String(emailId)))

  useEffect(() => {
    if (!email) return
    api(`/rag/search?q=${encodeURIComponent(email.subject + ' ' + email.body)}`).then(setRag)
    if (email.body?.toLowerCase().includes('trustpilot') || email.body?.toLowerCase().includes('g2')) {
      api('/intelligence/reputation?entity=MyCompany').then(setReputation)
    }
    api(`/agent/dry-run/${email.id}`, { method: 'POST' }).then(setDryRun)
  }, [email])

  if (!email) return <Layout><p>Loading…</p></Layout>

  return (
    <Layout>
      <button onClick={() => window.history.back()}>← Back</button>
      <h1>Thread Workspace</h1>
      <div className="thread-grid">
        <div className="panel">
          <h3>Email</h3>
          <p><b>{email.subject}</b></p>
          <p className="muted">{email.sender} · {email.timestamp}</p>
          <div>{highlightEntities(email.body, email.raw_entities)}</div>
        </div>
        <div className="panel">
          <h3>Timeline</h3>
          {(thread?.emails || []).map((m) => (
            <div key={m.id} className="timeline-item" style={{ borderColor: (m.sentiment_score || 0) < -0.3 ? 'var(--danger)' : 'var(--border)' }}>
              <small>{m.timestamp} — {sentimentBadge(m.sentiment_score)} {m.category}</small>
              <p><b>{m.subject}</b></p>
              <p>{m.body?.slice(0, 200)}…</p>
            </div>
          ))}
          {reputation && (
            <div style={{ marginTop: '1rem', padding: '0.5rem', background: '#0b1220', borderRadius: 6 }}>
              <b>Web Intelligence</b>
              <p>{reputation.data?.summary}</p>
            </div>
          )}
        </div>
        <div className="panel">
          <h3>Contact</h3>
          {contactInfo ? (
            <>
              <p>{contactInfo.name} · {contactInfo.status}</p>
              <p>Account: ${contactInfo.account_value?.toLocaleString()}</p>
              <p>Churn risk: {(contactInfo.churn_risk_score * 100).toFixed(0)}%</p>
            </>
          ) : <p>Unknown contact</p>}
          <hr />
          <button className="primary">Approve & Send</button>
          <button>Edit Draft</button>
          <button className="danger">Escalate</button>
          <button onClick={() => api(`/emails/${email.id}/bulk`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'spam' }) })}>Mark Spam</button>
        </div>
      </div>
      {dryRun && (
        <div className="panel" style={{ marginTop: '1rem' }}>
          <h3>Agent Reasoning</h3>
          {dryRun.trace?.map((s, i) => (
            <div key={i} className="trace">
              <div><b>Thought:</b> {s.thought}</div>
              <div><b>Action:</b> {s.action}</div>
              <div><b>Observation:</b> {s.observation}</div>
            </div>
          ))}
        </div>
      )}
      {rag && (
        <div className="panel" style={{ marginTop: '1rem' }}>
          <h3>RAG Context</h3>
          {rag.chunks?.map((c) => (
            <div key={c.id} style={{ marginBottom: '0.5rem' }}>
              <small>{c.source_doc} — score {c.score}</small>
              <p>{c.chunk_text?.slice(0, 200)}…</p>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}

function Analytics() {
  const [trend, setTrend] = useState([])
  const [breakdown, setBreakdown] = useState({})
  const [heatmap, setHeatmap] = useState([])
  const [atRisk, setAtRisk] = useState({})
  const [agent, setAgent] = useState({})
  const [sender, setSender] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams({ days: '365' })
    if (sender.trim()) params.set('sender', sender.trim())
    setLoading(true)
    setError(null)
    Promise.all([
      api(`/analytics/sentiment-trend?${params}`),
      api('/analytics/category-breakdown?days=365'),
      api('/analytics/response-heatmap'),
      api('/analytics/at-risk'),
      api('/analytics/agent-performance'),
    ])
      .then(([t, b, h, a, ag]) => {
        setTrend(t.series || [])
        setBreakdown(b.breakdown || {})
        setHeatmap((h.heatmap_by_hour || []).map((v, i) => ({ hour: i, count: v })))
        setAtRisk(a || {})
        setAgent(ag || {})
      })
      .catch((err) => setError(err.message || 'Failed to load analytics'))
      .finally(() => setLoading(false))
  }, [sender])

  const pieData = Object.entries(breakdown).map(([name, value]) => ({ name, value }))

  return (
    <Layout>
      <h1>Analytics Dashboard</h1>
      <input placeholder="Filter sender (optional)" value={sender} onChange={(e) => setSender(e.target.value)} style={{ maxWidth: 300, marginBottom: '1rem' }} />
      {loading && <p>Loading analytics…</p>}
      {error && <p style={{ color: '#ef4444' }}>Error: {error} — is the API running on port 8000?</p>}
      <div className="charts">
        <div className="panel">
          <h3>Sentiment Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trend}>
              <XAxis dataKey="date" stroke="#8b9cb3" />
              <YAxis domain={[-1, 1]} stroke="#8b9cb3" />
              <Tooltip />
              <Line type="monotone" dataKey="avg_sentiment" stroke="#3b82f6" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Category Breakdown</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Response Time Heatmap (by hour)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={heatmap}>
              <XAxis dataKey="hour" stroke="#8b9cb3" />
              <YAxis stroke="#8b9cb3" />
              <Tooltip />
              <Bar dataKey="count" fill="#22c55e" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Agent Performance</h3>
          <p>Auto-reply rate: {((agent.auto_reply_rate ?? 0) * 100).toFixed(1)}%</p>
          <p>Escalation rate: {((agent.escalation_rate ?? 0) * 100).toFixed(1)}%</p>
          <p>Avg confidence: {agent.average_confidence ?? '—'}</p>
        </div>
      </div>
      <div className="panel" style={{ marginTop: '1rem' }}>
        <h3>At-Risk Accounts</h3>
        <ul>{atRisk.high_churn_risk?.map((c) => <li key={c.email}>{c.email} — churn {c.score} — ${c.account_value}</li>)}</ul>
        <h4>Stale threads &gt;48h</h4>
        <ul>{atRisk.stale_threads_48h?.map((t) => <li key={t.thread_id}>{t.thread_id} ({t.sender})</li>)}</ul>
      </div>
    </Layout>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Inbox />} />
        <Route path="/thread/:contact/:emailId" element={<ThreadWorkspace />} />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </BrowserRouter>
  )
}
