import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../AuthContext'
import api from '../api'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer
} from 'recharts'
import {
  BarChart3, LogOut, Play, RefreshCw, Database,
  TrendingUp, Award, ChevronDown, ChevronUp, MessageSquare,
  CheckCircle, Loader2, Terminal, Upload, FileText, Users
} from 'lucide-react'

const METRIC_LABELS = {
  context_relevance: 'Context Relevance',
  faithfulness:      'Faithfulness',
  answer_relevance:  'Answer Relevance',
  answer_grounding:  'Answer Grounding',
}

const METRIC_COLORS = {
  context_relevance: '#3b82f6',
  faithfulness:      '#10b981',
  answer_relevance:  '#f59e0b',
  answer_grounding:  '#8b5cf6',
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-5">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-3xl font-bold" style={{ color }}>{typeof value === 'number' ? value.toFixed(3) : value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  )
}

function MetricBadge({ value }) {
  const color = value >= 0.7 ? 'text-green-400 bg-green-400/10 border-green-400/20'
              : value >= 0.5 ? 'text-amber-400 bg-amber-400/10 border-amber-400/20'
              : 'text-red-400 bg-red-400/10 border-red-400/20'
  return (
    <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${color}`}>
      {value.toFixed(2)}
    </span>
  )
}

export default function Admin() {
  const { logout } = useAuth()
  const [view, setView] = useState('admin')
  const [metrics, setMetrics] = useState(null)
  const [config, setConfig] = useState(null)
  const [collStats, setCollStats] = useState(null)
  const [running, setRunning] = useState(false)
  const [logs, setLogs] = useState([])
  const [expandQ, setExpandQ] = useState(null)
  const [activeRound, setActiveRound] = useState('baseline')
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState(null)
  const logRef = useRef(null)
  const fileRef = useRef(null)

  const load = async () => {
    const [m, c, s] = await Promise.all([
      api.get('/admin/metrics').catch(() => ({ data: null })),
      api.get('/admin/config').catch(() => ({ data: null })),
      api.get('/admin/collection-stats').catch(() => ({ data: null })),
    ])
    setMetrics(m.data?.error ? null : m.data)
    setConfig(c.data)
    setCollStats(s.data)
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setUploadMsg(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await api.post('/ingest', form)
      setUploadMsg({ ok: true, text: `✅ ${data.document} — ${data.chunk_count} pages indexed` })
      await load()
    } catch (err) {
      setUploadMsg({ ok: false, text: `❌ ${err.response?.data?.detail || err.message}` })
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => { logRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [logs])

  const runEval = async () => {
    setRunning(true)
    setLogs([])
    try {
      const resp = await fetch('/admin/run-eval', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      })
      const reader = resp.body.getReader()
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value)
        const parts = buf.split('\n\n')
        buf = parts.pop()
        for (const part of parts) {
          if (!part.startsWith('data:')) continue
          const payload = JSON.parse(part.slice(5).trim())
          if (payload.line !== undefined) setLogs(l => [...l, payload.line])
          if (payload.done) { await load(); setRunning(false) }
        }
      }
    } catch {
      setLogs(l => [...l, '❌ Connection error'])
      setRunning(false)
    }
  }

  const radarData = metrics ? Object.keys(METRIC_LABELS).map(k => ({
    metric: METRIC_LABELS[k].split(' ')[0],
    Baseline: metrics.baseline?.mean_scores?.[k] ?? 0,
    Improved: metrics.improved?.mean_scores?.[k] ?? 0,
  })) : []

  const barData = metrics ? Object.keys(METRIC_LABELS).map(k => ({
    name: METRIC_LABELS[k].split(' ')[0],
    Baseline: metrics.baseline?.mean_scores?.[k] ?? 0,
    Improved: metrics.improved?.mean_scores?.[k] ?? 0,
  })) : []

  const activeResults = metrics?.[activeRound]?.results ?? []

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">

      {/* Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-purple-600 flex items-center justify-center">
              <BarChart3 className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-white">PresentationRAG</span>
            <span className="text-xs bg-purple-500/10 text-purple-400 border border-purple-500/20 px-2 py-0.5 rounded-full">Admin</span>
          </div>

          <div className="flex items-center gap-4">
            {/* View toggle switch */}
            <div className="flex items-center bg-slate-800 border border-slate-700 rounded-xl p-1 gap-1">
              <button
                onClick={() => setView('admin')}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition font-medium ${
                  view === 'admin' ? 'bg-purple-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5" /> Admin
              </button>
              <button
                onClick={() => setView('user')}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition font-medium ${
                  view === 'user' ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Users className="w-3.5 h-3.5" /> User View
              </button>
            </div>

            <button onClick={logout}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition">
              <LogOut className="w-3.5 h-3.5" /> Sign out
            </button>
          </div>
        </div>
      </header>

      {/* ── USER VIEW (iframe) ─────────────────────────────────────────── */}
      {view === 'user' && (
        <div className="h-[calc(100vh-56px)]">
          <iframe src="/chat" className="w-full h-full border-0" title="User View" />
        </div>
      )}

      {/* ── ADMIN VIEW ────────────────────────────────────────────────── */}
      {view === 'admin' && (
        <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">

          {/* Upload PDF */}
          <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-6">
            <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-4">
              <Upload className="w-4 h-4 text-blue-400" /> Upload Presentation PDF
            </h3>
            <div className="flex items-center gap-4 flex-wrap">
              <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} />
              <button
                onClick={() => fileRef.current.click()}
                disabled={uploading}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2.5 rounded-xl transition"
              >
                {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                {uploading ? 'Ingesting...' : 'Choose PDF & Ingest'}
              </button>
              {uploadMsg && (
                <span className={`text-sm ${uploadMsg.ok ? 'text-green-400' : 'text-red-400'}`}>
                  {uploadMsg.text}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-3">
              PDF is parsed page-by-page, embedded, and stored in Qdrant. Collection stats refresh automatically.
            </p>
          </div>

          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Winner Round"    value={metrics?.winner?.round?.toUpperCase() ?? '—'} sub="highest mean avg score" color="#a855f7" />
            <StatCard label="Winner Avg Score" value={metrics?.winner?.mean_average ?? 0}           sub="across 5 metrics"       color="#3b82f6" />
            <StatCard label="Optimal top_k"   value={config?.settings?.top_k ?? '—'}               sub="from winner config"     color="#10b981" />
            <StatCard label="Indexed Chunks"  value={collStats?.vectors_count ?? '—'}              sub={collStats?.collection ?? 'Qdrant'} color="#f59e0b" />
          </div>

          {/* Winner badge */}
          {metrics?.winner && (
            <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-500/30 rounded-2xl p-5 flex items-center gap-4">
              <Award className="w-10 h-10 text-yellow-400 flex-shrink-0" />
              <div>
                <p className="text-sm font-semibold text-white">
                  Best Configuration: <span className="text-purple-400">{metrics.winner.round.toUpperCase()}</span>
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  top_k = <span className="text-white">{metrics.winner.settings.top_k}</span> &nbsp;·&nbsp;
                  threshold = <span className="text-white">{metrics.winner.settings.threshold}</span> &nbsp;·&nbsp;
                  prompt = <span className="text-white">{metrics.winner.settings.prompt}</span> &nbsp;·&nbsp;
                  avg score = <span className="text-green-400 font-mono">{metrics.winner.mean_average?.toFixed(3)}</span>
                </p>
              </div>
            </div>
          )}

          {/* Charts */}
          {metrics && (
            <div className="grid md:grid-cols-2 gap-6">
              <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-blue-400" /> Metric Radar — Baseline vs Improved
                </h3>
                <ResponsiveContainer width="100%" height={280}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#334155" />
                    <PolarAngleAxis dataKey="metric" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 1]} tick={{ fill: '#64748b', fontSize: 9 }} />
                    <Radar name="Baseline" dataKey="Baseline" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
                    <Radar name="Improved" dataKey="Improved" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.15} />
                    <Legend wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-6">
                <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-purple-400" /> Mean Score per Metric
                </h3>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={barData} margin={{ bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 10 }} />
                    <YAxis domain={[0, 1]} tick={{ fill: '#64748b', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }} labelStyle={{ color: '#e2e8f0' }} />
                    <Legend wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} />
                    <Bar dataKey="Baseline" fill="#3b82f6" radius={[4,4,0,0]} />
                    <Bar dataKey="Improved" fill="#8b5cf6" radius={[4,4,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Per-question results */}
          {metrics && (
            <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-green-400" /> Per-Question Results
                </h3>
                <div className="flex gap-2">
                  {['baseline', 'improved'].map(r => (
                    <button key={r} onClick={() => setActiveRound(r)}
                      className={`text-xs px-3 py-1.5 rounded-lg transition ${
                        activeRound === r ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                      }`}>
                      {r.charAt(0).toUpperCase() + r.slice(1)}
                      {metrics.winner?.round === r && ' 🏆'}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                {activeResults.map((r, i) => (
                  <div key={i} className="border border-slate-700/50 rounded-xl overflow-hidden">
                    <button
                      onClick={() => setExpandQ(expandQ === i ? null : i)}
                      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-700/30 transition text-left"
                    >
                      <span className="text-xs text-slate-500 font-mono w-4">Q{i+1}</span>
                      <span className="text-xs text-slate-400 flex-1">{r.type}</span>
                      <div className="flex gap-1.5 items-center">
                        {Object.keys(METRIC_LABELS).map(k => <MetricBadge key={k} value={r.metrics[k]} />)}
                      </div>
                      <span className="text-xs font-semibold text-white ml-2">avg {r.metrics.average.toFixed(2)}</span>
                      {expandQ === i ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
                    </button>

                    {expandQ === i && (
                      <div className="px-4 pb-4 space-y-3 border-t border-slate-700/50 pt-3">
                        <div>
                          <p className="text-xs text-slate-500 mb-1">Question</p>
                          <p className="text-sm text-slate-200">{r.question}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 mb-1">Answer</p>
                          <p className="text-sm text-slate-300 bg-slate-900/50 rounded-lg p-3 leading-relaxed">{r.answer}</p>
                        </div>
                        <div className="flex flex-wrap gap-4 text-xs">
                          <div><span className="text-slate-500">Pages Retrieved: </span><span className="text-blue-400">[{r.pages_retrieved?.join(', ')}]</span></div>
                          {r.limitations?.length > 0 && <div><span className="text-slate-500">Note: </span><span className="text-amber-400">{r.limitations[0]}</span></div>}
                        </div>
                        <div className="grid grid-cols-4 gap-2">
                          {Object.entries(METRIC_LABELS).map(([k, label]) => (
                            <div key={k} className="bg-slate-900/60 rounded-lg p-2 text-center">
                              <p className="text-xs text-slate-500 mb-1">{label.split(' ')[0]}</p>
                              <p className="text-sm font-semibold" style={{ color: METRIC_COLORS[k] }}>{r.metrics[k].toFixed(3)}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Run evaluation */}
          <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-amber-400" /> Run Evaluation Pipeline
              </h3>
              <div className="flex gap-2">
                <button onClick={load}
                  className="flex items-center gap-1.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-2 rounded-lg transition">
                  <RefreshCw className="w-3.5 h-3.5" /> Refresh
                </button>
                <button onClick={runEval} disabled={running}
                  className="flex items-center gap-1.5 text-xs bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg transition">
                  {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                  {running ? 'Running...' : 'Run Eval'}
                </button>
              </div>
            </div>
            <p className="text-xs text-slate-500 mb-3">
              6 questions × 2 rounds. Winner auto-selected by mean average score. ~15–30 min. Results refresh when done.
            </p>
            {logs.length > 0 && (
              <div className="bg-slate-950 rounded-xl border border-slate-700/50 p-4 h-56 overflow-y-auto font-mono text-xs text-slate-300 space-y-0.5">
                {logs.map((l, i) => (
                  <div key={i} className={l.includes('WINNER') ? 'text-yellow-400 font-semibold' : l.includes('ERROR') ? 'text-red-400' : ''}>
                    {l}
                  </div>
                ))}
                <div ref={logRef} />
              </div>
            )}
          </div>

          {/* System info */}
          <div className="bg-slate-800/60 border border-slate-700/50 rounded-2xl p-6">
            <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-4">
              <Database className="w-4 h-4 text-blue-400" /> System Info
            </h3>
            <div className="grid md:grid-cols-3 gap-4 text-xs">
              <div className="space-y-2">
                <p className="text-slate-500 font-medium uppercase tracking-wider">Qdrant Collection</p>
                {collStats && !collStats.error ? (
                  <div className="space-y-1 text-slate-300">
                    <div><span className="text-slate-500">Name: </span>{collStats.collection}</div>
                    <div><span className="text-slate-500">Vectors: </span>{collStats.vectors_count}</div>
                    <div><span className="text-slate-500">Points: </span>{collStats.points_count}</div>
                    <div className="flex items-center gap-1">
                      <span className="text-slate-500">Status: </span>
                      <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                      <span className="text-green-400">{collStats.status}</span>
                    </div>
                  </div>
                ) : <p className="text-red-400">{collStats?.error ?? 'Loading...'}</p>}
              </div>

              <div className="space-y-2">
                <p className="text-slate-500 font-medium uppercase tracking-wider">Winner Config</p>
                {config?.settings ? (
                  <div className="space-y-1 text-slate-300">
                    <div><span className="text-slate-500">top_k: </span>{config.settings.top_k}</div>
                    <div><span className="text-slate-500">threshold: </span>{config.settings.threshold}</div>
                    <div><span className="text-slate-500">prompt: </span>{config.settings.prompt}</div>
                    <div><span className="text-slate-500">round: </span><span className="text-purple-400">{config.round}</span></div>
                  </div>
                ) : <p className="text-slate-500">No eval run yet</p>}
              </div>

              <div className="space-y-2">
                <p className="text-slate-500 font-medium uppercase tracking-wider">Mean Scores</p>
                {metrics?.winner ? (
                  <div className="space-y-1.5">
                    {Object.keys(METRIC_LABELS).map(k => {
                      const val = metrics[metrics.winner.round]?.mean_scores?.[k] ?? 0
                      return (
                        <div key={k} className="flex items-center gap-2">
                          <span className="text-slate-500 w-6 text-right">{METRIC_LABELS[k].split(' ').map(w => w[0]).join('')}</span>
                          <div className="flex-1 bg-slate-700 rounded-full h-1.5">
                            <div className="h-1.5 rounded-full" style={{ width: `${val * 100}%`, background: METRIC_COLORS[k] }} />
                          </div>
                          <span className="text-slate-300 font-mono w-10 text-right">{val.toFixed(2)}</span>
                        </div>
                      )
                    })}
                  </div>
                ) : <p className="text-slate-500">Run evaluation first</p>}
              </div>
            </div>
          </div>

        </div>
      )}
    </div>
  )
}
