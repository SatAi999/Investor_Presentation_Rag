import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import { PrivateRoute } from './PrivateRoute'
import Login from './pages/Login'
import Chat  from './pages/Chat'
import Admin from './pages/Admin'

function RootRedirect() {
  const { isLoggedIn, role } = useAuth()
  if (!isLoggedIn) return <Navigate to="/login" replace />
  return <Navigate to={role === 'admin' ? '/admin' : '/chat'} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/chat" element={
            <PrivateRoute><Chat /></PrivateRoute>
          } />
          <Route path="/admin" element={
            <PrivateRoute requireRole="admin"><Admin /></PrivateRoute>
          } />
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
