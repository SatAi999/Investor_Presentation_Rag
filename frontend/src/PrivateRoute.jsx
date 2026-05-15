import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function PrivateRoute({ children, requireRole }) {
  const { isLoggedIn, role } = useAuth()
  if (!isLoggedIn) return <Navigate to="/login" replace />
  if (requireRole && role !== requireRole) return <Navigate to="/" replace />
  return children
}
