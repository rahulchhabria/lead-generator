import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Trash2, Mail, Shield, User as UserIcon } from 'lucide-react'
import { api, User, Invitation } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export default function TeamManagement() {
  const { user: currentUser, team } = useAuth()
  const queryClient = useQueryClient()
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteError, setInviteError] = useState('')

  const { data: members = [] } = useQuery<User[]>({
    queryKey: ['team-members'],
    queryFn: api.team.members,
  })

  const { data: invitations = [] } = useQuery<Invitation[]>({
    queryKey: ['team-invitations'],
    queryFn: api.team.invitations,
  })

  const inviteMutation = useMutation({
    mutationFn: (email: string) => api.team.invite(email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team-invitations'] })
      setInviteEmail('')
      setInviteError('')
    },
    onError: (e: Error) => setInviteError(e.message),
  })

  const cancelInviteMutation = useMutation({
    mutationFn: (id: string) => api.team.cancelInvitation(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['team-invitations'] }),
  })

  const removeMemberMutation = useMutation({
    mutationFn: (id: string) => api.team.removeMember(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['team-members'] }),
  })

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteEmail.trim()) return
    setInviteError('')
    inviteMutation.mutate(inviteEmail.trim())
  }

  const pendingInvitations = invitations.filter(i => i.status === 'pending')
  const activeMembers = members.filter(m => m.status === 'active')

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-gray-900">Team Management</h1>
        {team && (
          <p className="text-sm text-gray-500 mt-1">
            {team.name} &middot; @{team.allowed_domain}
          </p>
        )}
      </div>

      {/* Invite Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <UserPlus size={18} /> Invite Member
        </h2>
        <form onSubmit={handleInvite} className="flex gap-3">
          <div className="flex-1">
            <input
              type="email"
              value={inviteEmail}
              onChange={e => setInviteEmail(e.target.value)}
              placeholder={team ? `name@${team.allowed_domain}` : 'email@company.com'}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={inviteMutation.isPending || !inviteEmail.trim()}
            className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Mail size={16} />
            {inviteMutation.isPending ? 'Sending...' : 'Send Invite'}
          </button>
        </form>
        {inviteError && (
          <p className="mt-2 text-sm text-red-600">{inviteError}</p>
        )}
        {team && (
          <p className="mt-2 text-xs text-gray-500">
            Only @{team.allowed_domain} email addresses can be invited.
          </p>
        )}
      </div>

      {/* Members List */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">
          Members ({activeMembers.length})
        </h2>
        <div className="divide-y divide-gray-100">
          {activeMembers.map(member => (
            <div key={member.id} className="flex items-center justify-between py-3">
              <div className="flex items-center gap-3">
                {member.avatar_url ? (
                  <img
                    src={member.avatar_url}
                    alt={member.name}
                    className="w-8 h-8 rounded-full"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                    <UserIcon size={16} className="text-gray-500" />
                  </div>
                )}
                <div>
                  <p className="text-sm font-medium text-gray-900">{member.name}</p>
                  <p className="text-xs text-gray-500">{member.email}</p>
                </div>
                {member.role === 'admin' && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-brand-50 text-brand-700">
                    <Shield size={12} /> Admin
                  </span>
                )}
              </div>
              {member.id !== currentUser?.id && (
                <button
                  onClick={() => {
                    if (confirm(`Remove ${member.name} from the team?`)) {
                      removeMemberMutation.mutate(member.id)
                    }
                  }}
                  className="text-gray-400 hover:text-red-500 transition-colors p-1"
                  title="Remove member"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))}
          {activeMembers.length === 0 && (
            <p className="py-3 text-sm text-gray-500">No team members yet.</p>
          )}
        </div>
      </div>

      {/* Pending Invitations */}
      {pendingInvitations.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">
            Pending Invitations ({pendingInvitations.length})
          </h2>
          <div className="divide-y divide-gray-100">
            {pendingInvitations.map(inv => (
              <div key={inv.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{inv.email}</p>
                  <p className="text-xs text-gray-500">
                    Invited {new Date(inv.created_at).toLocaleDateString()} &middot;
                    Expires {new Date(inv.expires_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={() => cancelInviteMutation.mutate(inv.id)}
                  className="text-gray-400 hover:text-red-500 transition-colors p-1"
                  title="Cancel invitation"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
