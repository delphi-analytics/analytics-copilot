import React, { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, Clock, Database, Zap } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { useThemeStore } from '../store/theme'
import { analyticsApi, AnalyticsSummary, DailyStats, PopularQuery, IntentDistribution } from '../api/analytics'
import ReactECharts from 'echarts-for-react'

export default function AnalyticsPage() {
  const { user } = useAuthStore()
  const { theme } = useThemeStore()
  const navigate = useNavigate()

  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [dailyStats, setDailyStats] = useState<DailyStats[]>([])
  const [popularQueries, setPopularQueries] = useState<PopularQuery[]>([])
  const [intentDistribution, setIntentDistribution] = useState<IntentDistribution[]>([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  const isDark = theme === 'dark'

  useEffect(() => {
    loadAnalytics()
  }, [days])

  const loadAnalytics = async () => {
    setLoading(true)
    try {
      const [summaryData, dailyData, popularData, intentData] = await Promise.all([
        analyticsApi.getSummary(days),
        analyticsApi.getDailyStats(days),
        analyticsApi.getPopularQueries(10),
        analyticsApi.getIntentDistribution()
      ])
      setSummary(summaryData)
      setDailyStats(dailyData)
      setPopularQueries(popularData)
      setIntentDistribution(intentData)
    } catch (err) {
      console.error('Failed to load analytics:', err)
    } finally {
      setLoading(false)
    }
  }

  // Chart option for daily query volume
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
      data: dailyStats.map(d => {
        const date = new Date(d.date)
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      }),
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

  // Intent distribution chart
  const intentChartOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: isDark ? '#1f2937' : '#ffffff',
      borderColor: isDark ? '#374151' : '#e5e7eb',
      textStyle: { color: isDark ? '#f3f4f6' : '#111827' }
    },
    legend: {
      orient: 'horizontal' as const,
      bottom: '0%',
      textStyle: { color: isDark ? '#9ca3af' : '#6b7280' }
    },
    series: [
      {
        name: 'Query Types',
        type: 'pie' as const,
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 10,
          borderColor: isDark ? '#1f2937' : '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center' as const
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 20,
            fontWeight: 'bold' as const,
            color: isDark ? '#f3f4f6' : '#111827'
          }
        },
        labelLine: { show: false },
        data: intentDistribution.map(i => ({
          value: i.count,
          name: i.intent_type.replace('_', ' ')
        }))
      }
    ]
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      {/* Header */}
      <header className="bg-white dark:bg-zinc-800 border-b border-zinc-200 dark:border-zinc-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <BarChart3 className="w-8 h-8 text-blue-600" />
              <div>
                <h1 className="text-xl font-bold text-zinc-900 dark:text-white">Your Analytics</h1>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  Personal query insights for {user?.name || user?.email || 'Anonymous'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="px-3 py-1.5 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-700 text-zinc-900 dark:text-white"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>
              <button
                onClick={() => navigate('/')}
                className="text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
              >
                Back to Chat
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {loading ? (
          <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">Loading analytics...</div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                    <BarChart3 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-zinc-900 dark:text-white">
                      {summary?.total_queries || 0}
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
                      {summary?.cache_hit_rate || 0}%
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Cache Hit Rate</p>
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
                    <Clock className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-zinc-900 dark:text-white">
                      {summary?.avg_latency_ms || 0}ms
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Avg Latency</p>
                  </div>
                </div>
              </div>
              <div className="bg-white dark:bg-zinc-800 rounded-lg p-4 border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                    <Zap className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-zinc-900 dark:text-white">
                      {summary?.success_rate || 0}%
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">Success Rate</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {/* Daily Volume Chart */}
              <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4">
                <h3 className="text-lg font-semibold text-zinc-900 dark:text-white mb-4">
                  <TrendingUp className="w-5 h-5 inline mr-2" />
                  Daily Query Volume
                </h3>
                <ReactECharts option={dailyChartOption} style={{ height: '300px' }} />
              </div>

              {/* Intent Distribution Chart */}
              <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4">
                <h3 className="text-lg font-semibold text-zinc-900 dark:text-white mb-4">
                  <BarChart3 className="w-5 h-5 inline mr-2" />
                  Query Types
                </h3>
                <ReactECharts option={intentChartOption} style={{ height: '300px' }} />
              </div>
            </div>

            {/* Popular Queries */}
            <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 p-4">
              <h3 className="text-lg font-semibold text-zinc-900 dark:text-white mb-4">
                Your Most Asked Questions
              </h3>
              {popularQueries.length === 0 ? (
                <p className="text-zinc-500 dark:text-zinc-400 text-center py-8">
                  No queries yet. Start asking questions to see your analytics!
                </p>
              ) : (
                <div className="space-y-2">
                  {popularQueries.map((query, index) => (
                    <div
                      key={query.question}
                      className="flex items-center justify-between p-3 bg-zinc-50 dark:bg-zinc-700/50 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors cursor-pointer"
                      onClick={() => {
                        navigate('/')
                        setTimeout(() => {
                          // Could trigger the query automatically here
                        }, 100)
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <span className={`w-6 h-6 flex items-center justify-center text-xs font-bold rounded ${
                          index === 0 ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200' :
                          index === 1 ? 'bg-zinc-200 dark:bg-zinc-600 text-zinc-800 dark:text-zinc-200' :
                          index === 2 ? 'bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-200' :
                          'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200'
                        }`}>
                          {index + 1}
                        </span>
                        <span className="text-zinc-900 dark:text-white">{query.question}</span>
                      </div>
                      <span className="text-sm text-zinc-500 dark:text-zinc-400">
                        {query.count}x
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
