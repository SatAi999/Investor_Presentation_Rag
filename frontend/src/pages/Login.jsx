import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import api from '../api'
import { BarChart3, Lock, User } from 'lucide-react'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const form = new URLSearchParams()
      form.append('username', username)
      form.append('password', password)
      const { data } = await api.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      login(data.access_token, data.role)
      navigate(data.role === 'admin' ? '/admin' : '/chat')
    } catch {
      setError('Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 mb-4 shadow-lg shadow-blue-500/30">
            <BarChart3 className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">PresentationRAG</h1>
          <p className="text-slate-400 mt-2 text-sm">Investor Intelligence Platform</p>
        </div>

        {/* Card */}
        <div className="bg-slate-800/60 backdrop-blur border border-slate-700/50 rounded-2xl p-8 shadow-2xl">
          <h2 className="text-xl font-semibold text-white mb-6">Sign in to continue</h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm text-slate-400 mb-1.5">Username</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  className="w-full bg-slate-900/70 border border-slate-600 rounded-xl pl-10 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  placeholder="admin or user"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-slate-400 mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="password"
                  className="w-full bg-slate-900/70 border border-slate-600 rounded-xl pl-10 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl px-4 py-3 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition shadow-lg shadow-blue-500/20"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Demo creds hint */}
          <div className="mt-6 p-4 bg-slate-900/50 rounded-xl border border-slate-700/50">
            <p className="text-xs text-slate-500 font-medium mb-2">Demo credentials</p>
            <div className="space-y-1 text-xs text-slate-400">
              <div className="flex justify-between"><span>User:</span><code className="text-blue-400">user / user123</code></div>
              <div className="flex justify-between"><span>Admin:</span><code className="text-purple-400">admin / admin123</code></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
