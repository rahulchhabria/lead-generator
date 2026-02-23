import { Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LayoutDashboard, Building2, Users, Megaphone, Search, Menu, X, Shield, LogOut } from 'lucide-react'
import { useState } from 'react'
import { api } from './api/client'
import { useAuth } from './contexts/AuthContext'
import Dashboard from './pages/Dashboard'
import Enrichment from './pages/Enrichment'
import Campaigns from './pages/Campaigns'
import CampaignDetail from './pages/CampaignDetail'
import Accounts from './pages/Accounts'
import AccountDetail from './pages/AccountDetail'
import Contacts from './pages/Contacts'
import ContactDetail from './pages/ContactDetail'
import Login from './pages/Login'
import TeamManagement from './pages/TeamManagement'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/enrichment', label: 'Enrichment', icon: Search },
  { to: '/campaigns', label: 'Campaigns', icon: Megaphone },
  { to: '/accounts', label: 'Accounts', icon: Building2 },
  { to: '/contacts', label: 'Contacts', icon: Users },
]

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="animate-spin h-8 w-8 border-2 border-brand-600 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

function AuthenticatedApp() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, staleTime: 60_000 })
  const { user, team, logout } = useAuth()

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <aside className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 flex flex-col transform transition-transform duration-200 ease-in-out ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:relative lg:translate-x-0`}>
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-200">
          <div>
            <h1 className="text-base font-bold text-brand-700">Prospect Intel</h1>
            <p className="text-xs text-gray-500">{team?.name || 'B2B Research Platform'}</p>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden text-gray-400"><X size={20} /></button>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {navItems.map(({ to, label, icon: Icon, exact }) => (
            <NavLink key={to} to={to} end={exact} onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}>
              <Icon size={18} />{label}
            </NavLink>
          ))}
          {user?.role === 'admin' && (
            <NavLink to="/team" onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}>
              <Shield size={18} />Team
            </NavLink>
          )}
        </nav>
        {status && (
          <div className="px-4 py-4 border-t border-gray-200">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">API Keys</p>
            <div className="space-y-1.5">
              {Object.entries(status).map(([key, ok]) => (
                <div key={key} className="flex items-center gap-2 text-xs text-gray-600">
                  <span className={`inline-block w-2 h-2 rounded-full ${ok ? 'bg-green-400' : 'bg-red-400'}`} />
                  <span className="capitalize">{key}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {user && (
          <div className="px-4 py-4 border-t border-gray-200">
            <div className="flex items-center gap-3 mb-3">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.name} className="w-8 h-8 rounded-full" />
              ) : (
                <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center">
                  <span className="text-xs font-medium text-brand-700">
                    {user.name.charAt(0).toUpperCase()}
                  </span>
                </div>
              )}
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{user.name}</p>
                <p className="text-xs text-gray-500 truncate">{user.email}</p>
              </div>
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-lg transition-colors"
            >
              <LogOut size={16} />
              Sign Out
            </button>
          </div>
        )}
      </aside>
      {sidebarOpen && <div className="fixed inset-0 z-40 bg-black/30 lg:hidden" onClick={() => setSidebarOpen(false)} />}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="lg:hidden flex items-center h-14 px-4 bg-white border-b border-gray-200">
          <button onClick={() => setSidebarOpen(true)} className="text-gray-500"><Menu size={22} /></button>
          <span className="ml-3 font-semibold text-gray-900">Prospect Intelligence</span>
        </header>
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/enrichment" element={<Enrichment />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/campaigns/:id" element={<CampaignDetail />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/accounts/:id" element={<AccountDetail />} />
            <Route path="/contacts" element={<Contacts />} />
            <Route path="/contacts/:id" element={<ContactDetail />} />
            <Route path="/team" element={<TeamManagement />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={
        <ProtectedRoute>
          <AuthenticatedApp />
        </ProtectedRoute>
      } />
    </Routes>
  )
}
