import React, { useEffect, useState } from 'react'
import {
  Shield, Database, BarChart3, Users, HardDrive, CheckCircle, XCircle,
  RefreshCw, Eye, UserPlus, Mail, Key, Trash2, Edit2, ShieldCheck
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { useThemeStore } from '../store/theme'
import { adminApi, Approval } from '../api/admin'
import { analyticsApi, AnalyticsSummary, DailyStats, UserActivity, DatasourcePerformance, AdminSummary } from '../api/analytics'
import { usersApi, User, CreateUserRequest } from '../api/users'
import ReactECharts from 'echarts-for-react'

type Tab = 'approvals' | 'analytics' | 'users'

export default function AdminPage() {
  const { user } = useAuthStore()
  const { theme } = useThemeStore()
  const navigate = useNavigate()

  const [activeTab, setActiveTab] = useState<Tab>('users')
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [analytics, setAnalytics] = useState<AdminSummary | null>(null)
  const [dailyStats, setDailyStats] = useState<DailyStats[]>([])
  const [userActivity, setUserActivity] = useState<UserActivity[]>([])
  const [datasourcePerformance, setDatasourcePerformance] = useState<DatasourcePerformance[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [scanLoading, setScanLoading] = useState(false)
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // User creation state
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [newUser, setNewUser] = useState<CreateUserRequest>({
    email: '',
    name: '',
    role: 'business_analyst'
  })
  const [createUserLoading, setCreateUserLoading] = useState(false)
  const [createdUserPassword, setCreatedUserPassword] = useState<string | null>(null)

  const isDark = theme === 'dark'

  // Check if user has admin role (only admins can manage users)
  const isAdmin = user?.role === 'admin'

  // Business analysts and admins can see approvals and analytics
  const canAccess = isAdmin || user?.role === 'business_analyst'

  useEffect(() => {
    if (!canAccess) {
      navigate('/')
      return
    }
    if (isAdmin) {
      loadUsers()
    }
    loadApprovals()
    loadAnalytics()
  }, [canAccess, isAdmin, navigate])

  const loadUsers = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await usersApi.listUsers()
      setUsers(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  const loadApprovals = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await adminApi.getApprovals()
      setApprovals(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load approvals')
    } finally {
      setLoading(false)
    }
  }

  const loadAnalytics = async () => {
    try {
      const [summary, daily, usersData, datasources] = await Promise.all([
        analyticsApi.getAdminSummary(30),
        analyticsApi.getDailyStats(30),
        analyticsApi.getUserActivity(30),
        analyticsApi.getDatasourcePerformance(30)
      ])
      setAnalytics(summary)
      setDailyStats(daily)
      setUserActivity(usersData)
      setDatasourcePerformance(datasources)
    } catch (err) {
      console.error('Failed to load analytics:', err)
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateUserLoading(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const result = await usersApi.createUser(newUser)
      setCreatedUserPassword(result.temp_password)
      setSuccessMessage(result.message)
      setShowCreateUser(false)
      setNewUser({ email: '', name: '', role: 'business_analyst' })
      await loadUsers()
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to create user'
      setError(errorMsg)
    } finally {
      setCreateUserLoading(false)
    }
  }

  const handleDeleteUser = async (userId: string, userName: string) => {
    if (!confirm(`Are you sure you want to delete user "${userName}"?`)) {
      return
    }

    try {
      await usersApi.deleteUser(userId)
      setSuccessMessage('User deleted successfully')
      await loadUsers()
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to delete user'
      setError(errorMsg)
    }
  }

  const handleResetPassword = async (email: string) => {
    try {
      const result = await usersApi.resetPassword(email)
      setSuccessMessage(`Password reset for ${email}. New password: ${result.temp_password}`)
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to reset password'
      setError(errorMsg)
    }
  }

  const handleToggleUserStatus = async (userId: string, currentStatus: boolean) => {
    try {
      await usersApi.updateUser(userId, { is_active: !currentStatus })
      setSuccessMessage(`User ${!currentStatus ? 'activated' : 'deactivated'} successfully`)
      await loadUsers()
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to update user'
      setError(errorMsg)
    }
  }

  const handleApprove = async (id: string) => {
    try {
      await adminApi.approveChange(id)
      await loadApprovals()
      setSelectedApproval(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to approve change')
    }
  }

  const handleReject = async (id: string) => {
    const reason = prompt('Reason for rejection (optional):')
    try {
      await adminApi.rejectChange(id, reason || undefined)
      await loadApprovals()
      setSelectedApproval(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reject change')
    }
  }

  const handleTriggerScan = async () => {
    setScanLoading(true)
    try {
      const result = await adminApi.triggerScan()
      if (result.status === 'no_changes') {
        setSuccessMessage('No schema changes detected.')
      } else if (result.status === 'approval_created') {
        setSuccessMessage('Schema scan complete. New approval created.')
        await loadApprovals()
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to trigger scan')
    } finally {
      setScanLoading(false)
    }
  }

  // Chart options for daily query volume
  const dailyChartOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: isDark ? '#1f2937' : '#ffffff',
      borderColor: isDark ? '#374151' : '#e5e7eb',
      textStyle: { color: isDark ? '#f3f4f6' : '#111827' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category' as const,
      data: dailyStats.map(d => d.date),
      axisLine: { lineStyle: { color: isDark ? '#4b5563' : '#d1d5db' } },
      axisLabel: { color: isDark ? '#9ca3af' : '#6b7280', rotate: 45 }
    },
    yAxis: {
      type: 'value' as const,
      axisLine: { lineStyle: { color: isDark ? '#4b5563' : '#d1d5db' } },
      axisLabel: { color: isDark ? '#9ca3af' : '#6b7280' },
      splitLine: { lineStyle: { color: isDark ? '#374151' : '#e5e7eb' } }
    },
    series: [
      {
        name: 'Queries',
        type: 'line' as const,
        data: dailyStats.map(d => d.count),
        smooth: true,
        itemStyle: { color: '#3b82f6' },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
              { offset: 1, color: 'rgba(59, 130, 246, 0)' }
            ]
          }
        }
      }
    ]
  }

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'admin': return 'bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200'
      case 'business_analyst': return 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200'
      case 'team_member': return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
      case 'non_tech_user': return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
      default: return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
    }
  }

  const getRoleLabel = (role: string) => {
    switch (role) {
      case 'admin': return 'Admin'
      case 'business_analyst': return 'Business Analyst'
      case 'team_member': return 'Team Member'
      case 'non_tech_user': return 'Non-Tech User'
      default: return role
    }
  }

  if (!canAccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-900">
        <div className="text-center">
          <Shield className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white mb-2">Access Denied</h1>
          <p className="text-zinc-600 dark:text-zinc-400">You don't have permission to access the admin panel.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      {/* Header */}
      <header className="bg-white dark:bg-zinc-800 border-b border-zinc-200 dark:border-zinc-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <Shield className="w-8 h-8 text-blue-600" />
              <div>
                <h1 className="text-xl font-bold text-zinc-900 dark:text-white">Admin Panel</h1>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  {isAdmin ? 'Full Admin Access' : 'Business Analyst Access'}
                </p>
              </div>
            </div>
            <button
              onClick={() => navigate('/')}
              className="text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              Back to Chat
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <div className="flex gap-4 border-b border-zinc-200 dark:border-zinc-700">
          {isAdmin && (
            <button
              onClick={() => setActiveTab('users')}
              className={`px-4 py-2 font-medium border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === 'users'
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200'
              }`}
            >
              <Users className="w-4 h-4" />
              Users
              {users.length > 0 && (
                <span className="ml-1 px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full">
                  {users.length}
                </span>
              )}
            </button>
          )}
          <button
            onClick={() => setActiveTab('approvals')}
            className={`px-4 py-2 font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'approvals'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200'
            }`}
          >
            Approval Queue
            {approvals.length > 0 && (
              <span className="ml-1 px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full">
                {approvals.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-4 py-2 font-medium border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === 'analytics'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            System Analytics
          </button>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {error && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 rounded-lg flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="ml-4 underline">Dismiss</button>
          </div>
        )}

        {successMessage && (
          <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200 rounded-lg flex items-center justify-between">
            <span>{successMessage}</span>
            <button onClick={() => setSuccessMessage(null)} className="ml-4 underline">Dismiss</button>
          </div>
        )}

        {activeTab === 'users' && isAdmin && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">
                User Management
              </h2>
              <button
                onClick={() => setShowCreateUser(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                <UserPlus className="w-4 h-4" />
                Add User
              </button>
            </div>

            {loading ? (
              <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">Loading users...</div>
            ) : users.length === 0 ? (
              <div className="text-center py-12 bg-white dark:bg-zinc-800 rounded-lg">
                <Users className="w-12 h-12 text-zinc-400 mx-auto mb-4" />
                <p className="text-zinc-600 dark:text-zinc-400">No users found</p>
              </div>
            ) : (
              <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-zinc-50 dark:bg-zinc-900">
                    <tr>
                      <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase">User</th>
                      <th className="text-left py-3 px-4 text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase">Role</th>
                      <th className="text-center py-3 px-4 text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase">Status</th>
                      <th className="text-right py-3 px-4 text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                    {users.map((u) => (
                      <tr key={u.id} className={u.id === user?.id ? 'bg-blue-50 dark:bg-blue-900/10' : ''}>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                              <span className="text-white text-xs font-medium">
                                {u.name?.charAt(0).toUpperCase() || u.email.charAt(0).toUpperCase()}
                              </span>
                            </div>
                            <div>
                              <p className="font-medium text-zinc-900 dark:text-white">{u.name}</p>
                              <p className="text-sm text-zinc-500 dark:text-zinc-400">{u.email}</p>
                              {u.id === user?.id && (
                                <span className="text-xs text-blue-600 dark:text-blue-400">(You)</span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${getRoleBadgeColor(u.role)}`}>
                            {getRoleLabel(u.role)}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full ${
                            u.is_active
                              ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
                              : 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200'
                          }`}>
                            {u.is_active ? (
                              <>
                                <CheckCircle className="w-3 h-3" />
                                Active
                              </>
                            ) : (
                              <>
                                <XCircle className="w-3 h-3" />
                                Inactive
                              </>
                            )}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center justify-end gap-1">
                            {u.id !== user?.id && (
                              <>
                                <button
                                  onClick={() => handleToggleUserStatus(u.id, u.is_active)}
                                  className={`p-2 rounded-lg transition-colors ${
                                    u.is_active
                                      ? 'hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 hover:text-red-700'
                                      : 'hover:bg-green-50 dark:hover:bg-green-900/20 text-green-600 hover:text-green-700'
                                  }`}
                                  title={u.is_active ? 'Deactivate user' : 'Activate user'}
                                >
                                  {u.is_active ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
                                </button>
                                <button
                                  onClick={() => handleResetPassword(u.email)}
                                  className="p-2 hover:bg-yellow-50 dark:hover:bg-yellow-900/20 text-yellow-600 hover:text-yellow-700 rounded-lg transition-colors"
                                  title="Reset password"
                                >
                                  <Key className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => handleDeleteUser(u.id, u.name)}
                                  className="p-2 hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 hover:text-red-700 rounded-lg transition-colors"
                                  title="Delete user"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'approvals' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">
                Pending Approvals
              </h2>
              <button
                onClick={handleTriggerScan}
                disabled={scanLoading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${scanLoading ? 'animate-spin' : ''}`} />
                Trigger Schema Scan
              </button>
            </div>

            {loading ? (
              <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">Loading...</div>
            ) : approvals.length === 0 ? (
              <div className="text-center py-12 bg-white dark:bg-zinc-800 rounded-lg">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
                <p className="text-zinc-600 dark:text-zinc-400">No pending approvals</p>
              </div>
            ) : (
              <div className="grid gap-4">
                {approvals.map((approval) => (
                  <div
                    key={approval.id}
                    className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                            approval.change_type === 'db_schema'
                              ? 'bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200'
                              : 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200'
                          }`}>
                            {approval.change_type}
                          </span>
                          <span className="text-xs text-zinc-500 dark:text-zinc-400">
                            {new Date(approval.created_at).toLocaleString()}
                          </span>
                        </div>
                        <h3 className="font-semibold text-zinc-900 dark:text-white mb-1">
                          {approval.title}
                        </h3>
                        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
                          {approval.description}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedApproval(approval)}
                          className="p-2 text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded-lg transition-colors"
                          title="View details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleApprove(approval.id)}
                          className="p-2 text-green-600 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-lg transition-colors"
                          title="Approve"
                        >
                          <CheckCircle className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => handleReject(approval.id)}
                          className="p-2 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                          title="Reject"
                        >
                          <XCircle className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'analytics' && analytics && (
          <div>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                    <BarChart3 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-zinc-900 dark:text-white">
                      {analytics.total_queries}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Total Queries</p>
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                    <Database className="w-5 h-5 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-zinc-900 dark:text-white">
                      {analytics.cache_hit_rate}%
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Cache Hit Rate</p>
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                    <Users className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-zinc-900 dark:text-white">
                      {analytics.unique_users}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Active Users</p>
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
                    <HardDrive className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-zinc-900 dark:text-white">
                      {analytics.avg_latency_ms}ms
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Avg Latency</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Daily Chart */}
            <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4 mb-6">
              <h3 className="text-lg font-semibold text-zinc-900 dark:text-white mb-4">
                Daily Query Volume (30 days)
              </h3>
              <ReactECharts option={dailyChartOption} style={{ height: '300px' }} />
            </div>

            {/* User Activity Table */}
            <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4">
              <h3 className="text-lg font-semibold text-zinc-900 dark:text-white mb-4">
                User Activity
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 dark:border-zinc-700">
                      <th className="text-left py-2 px-3 text-zinc-500 dark:text-zinc-400 font-medium">User</th>
                      <th className="text-right py-2 px-3 text-zinc-500 dark:text-zinc-400 font-medium">Queries</th>
                      <th className="text-right py-2 px-3 text-zinc-500 dark:text-zinc-400 font-medium">Avg Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {userActivity.map((user) => (
                      <tr key={user.user_id} className="border-b border-zinc-100 dark:border-zinc-700">
                        <td className="py-2 px-3 text-zinc-900 dark:text-white">{user.user_id}</td>
                        <td className="py-2 px-3 text-right text-zinc-600 dark:text-zinc-400">{user.query_count}</td>
                        <td className="py-2 px-3 text-right text-zinc-600 dark:text-zinc-400">{user.avg_latency_ms}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Create User Modal */}
      {showCreateUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className={`bg-white dark:bg-zinc-800 rounded-xl max-w-md w-full shadow-2xl`}>
            <div className="p-6 border-b border-zinc-200 dark:border-zinc-700 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                  <UserPlus className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                </div>
                <h3 className="text-lg font-semibold text-zinc-900 dark:text-white">Create New User</h3>
              </div>
              <button
                onClick={() => setShowCreateUser(false)}
                className={`p-1 rounded ${isDark ? 'hover:bg-zinc-700' : 'hover:bg-zinc-100'}`}
              >
                <XCircle className={`w-5 h-5 ${isDark ? 'text-zinc-400' : 'text-zinc-600'}`} />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  Full Name
                </label>
                <input
                  type="text"
                  value={newUser.name}
                  onChange={(e) => setNewUser({ ...newUser, name: e.target.value })}
                  placeholder="Enter user's full name"
                  className="w-full px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border border-zinc-200 dark:border-zinc-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-zinc-900 dark:text-white"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  placeholder="user@example.com"
                  className="w-full px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border border-zinc-200 dark:border-zinc-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-zinc-900 dark:text-white"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  Role
                </label>
                <select
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  className="w-full px-4 py-2 bg-zinc-50 dark:bg-zinc-700/50 border border-zinc-200 dark:border-zinc-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-zinc-900 dark:text-white"
                >
                  <option value="business_analyst">Business Analyst (Full Access)</option>
                  <option value="team_member">Team Member (Read-only)</option>
                  <option value="non_tech_user">Non-Tech User (No SQL)</option>
                  <option value="admin">Admin (All Permissions)</option>
                </select>
              </div>

              <div className={`p-4 rounded-lg ${isDark ? 'bg-zinc-700' : 'bg-zinc-50'}`}>
                <div className="flex items-start gap-2">
                  <Mail className={`w-5 h-5 mt-0.5 ${isDark ? 'text-zinc-400' : 'text-zinc-600'}`} />
                  <div className="text-sm">
                    <p className={`font-medium ${isDark ? 'text-white' : 'text-zinc-900'}`}>Account Setup</p>
                    <p className={`mt-1 ${isDark ? 'text-zinc-400' : 'text-zinc-600'}`}>
                      A temporary password will be generated. You'll need to share it with the user securely.
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateUser(false)}
                  className={`flex-1 px-4 py-2 rounded-lg font-medium transition-colors ${
                    isDark
                      ? 'bg-zinc-700 text-white hover:bg-zinc-600'
                      : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'
                  }`}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createUserLoading}
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {createUserLoading ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <UserPlus className="w-4 h-4" />
                      Create User
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* User Created Success Modal */}
      {createdUserPassword && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className={`bg-white dark:bg-zinc-800 rounded-xl max-w-md w-full shadow-2xl`}>
            <div className="p-6 text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="text-xl font-semibold text-zinc-900 dark:text-white mb-2">
                User Created Successfully!
              </h3>
              <p className={`text-sm ${isDark ? 'text-zinc-400' : 'text-zinc-600'} mb-6`}>
                An email has been sent to <span className="font-medium text-zinc-900 dark:text-white">{newUser.email}</span> with their login credentials.
              </p>

              <div className={`p-4 rounded-lg ${isDark ? 'bg-zinc-700' : 'bg-zinc-50'} mb-6`}>
                <p className={`text-xs font-medium uppercase ${isDark ? 'text-zinc-400' : 'text-zinc-500'} mb-2`}>Temporary Password</p>
                <div className="flex items-center justify-center gap-2">
                  <code className="text-lg font-mono tracking-wider text-blue-600 dark:text-blue-400">
                    {createdUserPassword}
                  </code>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(createdUserPassword)
                      setSuccessMessage('Password copied to clipboard!')
                    }}
                    className="p-1 hover:bg-zinc-200 dark:hover:bg-zinc-600 rounded"
                    title="Copy password"
                  >
                    📋
                  </button>
                </div>
                <p className={`text-xs mt-2 ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
                  Share this password securely with the user. They can change it after logging in.
                </p>
              </div>

              <button
                onClick={() => setCreatedUserPassword(null)}
                className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Diff Modal */}
      {selectedApproval && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-zinc-800 rounded-lg max-w-2xl w-full max-h-[80vh] overflow-auto">
            <div className="p-4 border-b border-zinc-200 dark:border-zinc-700 flex items-center justify-between">
              <h3 className="font-semibold text-zinc-900 dark:text-white">Change Details</h3>
              <button
                onClick={() => setSelectedApproval(null)}
                className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
              >
                ✕
              </button>
            </div>
            <div className="p-4">
              <pre className="bg-zinc-100 dark:bg-zinc-900 p-4 rounded text-sm overflow-auto max-h-96">
                {JSON.stringify(selectedApproval.diff_data, null, 2)}
              </pre>
            </div>
            <div className="p-4 border-t border-zinc-200 dark:border-zinc-700 flex justify-end gap-2">
              <button
                onClick={() => setSelectedApproval(null)}
                className="px-4 py-2 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleReject(selectedApproval.id)}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
              >
                Reject
              </button>
              <button
                onClick={() => handleApprove(selectedApproval.id)}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
              >
                Approve
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
