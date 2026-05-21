import React, { useEffect, useState } from 'react'
import { Shield, Database, BarChart3, Users, HardDrive, CheckCircle, XCircle, RefreshCw, Eye } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { useThemeStore } from '../store/theme'
import { adminApi, Approval } from '../api/admin'
import { analyticsApi, AnalyticsSummary, DailyStats, UserActivity, DatasourcePerformance, AdminSummary } from '../api/analytics'
import ReactECharts from 'echarts-for-react'

type Tab = 'approvals' | 'analytics'

export default function AdminPage() {
  const { user } = useAuthStore()
  const { theme } = useThemeStore()
  const navigate = useNavigate()

  const [activeTab, setActiveTab] = useState<Tab>('approvals')
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [analytics, setAnalytics] = useState<AdminSummary | null>(null)
  const [dailyStats, setDailyStats] = useState<DailyStats[]>([])
  const [userActivity, setUserActivity] = useState<UserActivity[]>([])
  const [datasourcePerformance, setDatasourcePerformance] = useState<DatasourcePerformance[]>([])
  const [loading, setLoading] = useState(false)
  const [scanLoading, setScanLoading] = useState(false)
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isDark = theme === 'dark'

  // Check if user has admin or business_analyst role
  const canAccess = user?.role === 'admin' || user?.role === 'business_analyst'

  useEffect(() => {
    if (!canAccess) {
      navigate('/')
      return
    }
    loadApprovals()
    loadAnalytics()
  }, [canAccess, navigate])

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
      const [summary, daily, users, datasources] = await Promise.all([
        analyticsApi.getAdminSummary(30),
        analyticsApi.getDailyStats(30),
        analyticsApi.getUserActivity(30),
        analyticsApi.getDatasourcePerformance(30)
      ])
      setAnalytics(summary)
      setDailyStats(daily)
      setUserActivity(users)
      setDatasourcePerformance(datasources)
    } catch (err) {
      console.error('Failed to load analytics:', err)
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
        alert('No schema changes detected.')
      } else if (result.status === 'approval_created') {
        alert('Schema scan complete. New approval created.')
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
                  {user?.role === 'admin' ? 'Full Admin Access' : 'Business Analyst Access'}
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
          <button
            onClick={() => setActiveTab('approvals')}
            className={`px-4 py-2 font-medium border-b-2 transition-colors ${
              activeTab === 'approvals'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200'
            }`}
          >
            Approval Queue
            {approvals.length > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full">
                {approvals.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-4 py-2 font-medium border-b-2 transition-colors ${
              activeTab === 'analytics'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200'
            }`}
          >
            System Analytics
          </button>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {error && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 rounded-lg">
            {error}
            <button onClick={() => setError(null)} className="ml-4 underline">Dismiss</button>
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
