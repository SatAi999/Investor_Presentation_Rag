import { createContext, useContext, useState } from 'react'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [role,  setRole]  = useState(() => localStorage.getItem('role'))

  const login = (token, role) => {
    localStorage.setItem('token', token)
    localStorage.setItem('role', role)
    setToken(token)
    setRole(role)
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    setToken(null)
    setRole(null)
  }

  return (
    <AuthCtx.Provider value={{ token, role, login, logout, isLoggedIn: !!token }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)
