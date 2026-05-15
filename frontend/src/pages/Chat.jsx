import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import api from '../api'
import {
  Send, Upload, FileText, LogOut, BarChart3,
  ChevronDown, ChevronUp, BookOpen, AlertTriangle, Loader2
} from 'lucide-react'

function Message({ msg }) {
  const [openCite, setOpenCite] = useState(null)
  const isUser = msg.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mt-1">
          <BarChart3 className="w-4 h-4 text-white" />
        </div>
      )}

      <div className={`max-w-2xl space-y-2 ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-sm'
            : 'bg-slate-800 text-slate-100 border border-slate-700 rounded-bl-sm'
        }`}>
          {msg.content}
        </div>

        {msg.limitations?.map((l, i) => (
          <div key={i} className="flex items-start gap-2 text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-xl px-3 py-2">
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            {l}
          </div>
        ))}

        {msg.citations?.length > 0 && (
          <div className="w-full space-y-1">
            <p className="text-xs text-slate-500 flex items-center gap-1">
              <BookOpen className="w-3 h-3" /> {msg.citations.length} source{msg.citations.length > 1 ? 's' : ''}
            </p>
            {msg.citations.map((c, i) => (
              <div key={i} className="bg-slate-800/60 border border-slate-700/50 rounded-xl overflow-hidden">
                <button
                  onClick={() => setOpenCite(openCite === i ? null : i)}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs text-slate-300 hover:bg-slate-700/50 transition"
                >
                  <span className="font-medium">📄 Page {c.page}</span>
                  {openCite === i ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
                {openCite === i && (
                  <div className="px-3 pb-3 text-xs text-slate-400 border-t border-slate-700/50 pt-2 leading-relaxed">
                    {c.excerpt}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Chat() {
  const { logout, role } = useAuth()
  const navigate = useNavigate()
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! Upload an investor presentation PDF and ask me anything about it.' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [docInfo, setDocInfo] = useState(null)
  const [topK, setTopK] = useState(5)
  const [ingested, setIngested] = useState(false)
  const bottomRef = useRef(null)
  const fileRef = useRef(null)

  // Auto-load winner top_k if available
  useEffect(() => {
    api.get('/admin/config').then(r => {
      if (r.data?.settings?.top_k) setTopK(r.data.settings.top_k)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await api.post('/ingest', form)
      setDocInfo(data)
      setIngested(true)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `✅ **${data.document}** ingested — ${data.chunk_count} pages indexed. Ask away!`
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `❌ Upload failed: ${err.response?.data?.detail || err.message}`
      }])
    } finally {
      setUploading(false)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const question = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: question }])
    setLoading(true)
    try {
      const { data } = await api.post('/query', { question, top_k: topK })
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        citations: data.citations,
        limitations: data.limitations,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `❌ Error: ${err.response?.data?.detail || err.message}`
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-500" />
            <span className="font-semibold text-white">PresentationRAG</span>
            {docInfo && (
              <span className="ml-3 text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2.5 py-1 rounded-full">
                {docInfo.document} · {docInfo.chunk_count}p
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">top_k={topK}</span>
            {role === 'admin' && (
              <button onClick={() => navigate('/admin')}
                className="text-xs text-purple-400 hover:text-purple-300 transition">
                Admin ↗
              </button>
            )}
            <button onClick={logout}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition">
              <LogOut className="w-3.5 h-3.5" /> Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 max-w-5xl mx-auto w-full gap-0">
        {/* Sidebar */}
        <aside className="w-64 flex-shrink-0 border-r border-slate-800 p-4 space-y-6 hidden md:block">
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Upload PDF</p>
            <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} />
            <button
              onClick={() => fileRef.current.click()}
              disabled={uploading}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:cursor-not-allowed text-white text-sm font-medium py-2.5 rounded-xl transition"
            >
              {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {uploading ? 'Uploading...' : 'Upload PDF'}
            </button>
            {ingested && docInfo && (
              <div className="mt-3 p-3 bg-green-500/10 border border-green-500/20 rounded-xl text-xs text-green-400 space-y-1">
                <div className="flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" /><span className="font-medium">{docInfo.document}</span></div>
                <div>{docInfo.chunk_count} pages indexed</div>
              </div>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Retrieval</p>
            <label className="text-xs text-slate-400 block mb-2">Chunks to retrieve: <span className="text-white font-medium">{topK}</span></label>
            <input
              type="range" min={1} max={10} value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              className="w-full accent-blue-500"
            />
            <div className="flex justify-between text-xs text-slate-600 mt-1"><span>1</span><span>10</span></div>
          </div>
        </aside>

        {/* Chat area */}
        <main className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.map((m, i) => <Message key={i} msg={m} />)}
            {loading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                  <BarChart3 className="w-4 h-4 text-white" />
                </div>
                <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2 text-slate-400 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" /> Thinking...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input bar */}
          <div className="border-t border-slate-800 p-4">
            <div className="flex gap-3 bg-slate-800/60 border border-slate-700 rounded-2xl px-4 py-3">
              <input
                className="flex-1 bg-transparent text-white placeholder-slate-500 text-sm focus:outline-none"
                placeholder={ingested ? "Ask a question about the presentation..." : "Upload a PDF first to start asking questions"}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                disabled={!ingested || loading}
              />
              <button
                onClick={handleSend}
                disabled={!ingested || loading || !input.trim()}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed p-2 rounded-xl transition"
              >
                <Send className="w-4 h-4 text-white" />
              </button>
            </div>
            <p className="text-xs text-slate-600 mt-2 text-center">Answers grounded in document context with page citations</p>
          </div>
        </main>
      </div>
    </div>
  )
}
