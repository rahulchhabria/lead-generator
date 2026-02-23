import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleLogin, CredentialResponse } from '@react-oauth/google'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { login, signup, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [teamName, setTeamName] = useState('')
  const [pendingToken, setPendingToken] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isAuthenticated) navigate('/', { replace: true })
  }, [isAuthenticated, navigate])

  const handleGoogleSuccess = async (response: CredentialResponse) => {
    if (!response.credential) {
      setError('Google sign-in failed. Please try again.')
      return
    }

    if (mode === 'login') {
      setLoading(true)
      setError('')
      try {
        await login(response.credential)
        navigate('/')
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Login failed')
      } finally {
        setLoading(false)
      }
    } else {
      // For signup, we need the team name first
      if (!teamName.trim()) {
        setPendingToken(response.credential)
        setError('Please enter a team name first, then click Create Team.')
        return
      }
      setLoading(true)
      setError('')
      try {
        await signup(response.credential, teamName.trim())
        navigate('/')
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Signup failed')
      } finally {
        setLoading(false)
      }
    }
  }

  const handleCreateTeam = async () => {
    if (!pendingToken || !teamName.trim()) return
    setLoading(true)
    setError('')
    try {
      await signup(pendingToken, teamName.trim())
      navigate('/')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-brand-700">Prospect Intelligence</h1>
          <p className="text-sm text-gray-500 mt-1">B2B Research Platform</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          {/* Mode tabs */}
          <div className="flex rounded-lg bg-gray-100 p-1 mb-6">
            <button
              onClick={() => { setMode('login'); setError(''); setPendingToken(null) }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'login' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode('signup'); setError(''); setPendingToken(null) }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'signup' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Create Team
            </button>
          </div>

          {mode === 'login' ? (
            <div>
              <p className="text-sm text-gray-600 mb-6">
                Sign in with your Google workspace account. You must have an invitation from your team admin.
              </p>
              <div className="flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => setError('Google sign-in failed')}
                  size="large"
                  width="320"
                  text="signin_with"
                />
              </div>
            </div>
          ) : (
            <div>
              <p className="text-sm text-gray-600 mb-4">
                Create a new team for your company. Your email domain will be used to restrict team membership.
              </p>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Team Name
                </label>
                <input
                  type="text"
                  value={teamName}
                  onChange={e => setTeamName(e.target.value)}
                  placeholder="e.g., Sentry"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Only users with your email domain will be able to join.
                </p>
              </div>
              {pendingToken ? (
                <button
                  onClick={handleCreateTeam}
                  disabled={loading || !teamName.trim()}
                  className="w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Creating team...' : 'Create Team'}
                </button>
              ) : (
                <div className="flex justify-center">
                  <GoogleLogin
                    onSuccess={handleGoogleSuccess}
                    onError={() => setError('Google sign-in failed')}
                    size="large"
                    width="320"
                    text="signup_with"
                  />
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {loading && (
            <div className="mt-4 flex justify-center">
              <div className="animate-spin h-5 w-5 border-2 border-brand-600 border-t-transparent rounded-full" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
