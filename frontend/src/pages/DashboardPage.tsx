import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, LayoutDashboard, Trash2, RefreshCw, ChevronLeft, BarChart3, Table } from 'lucide-react'
import { useThemeStore } from '../store/theme'
import { useAuthStore } from '../store/auth'
import { dashboardsApi, type Dashboard, type DashboardDetail, type DashboardChart } from '../api/dashboards'
import { ChartRenderer } from '../components/Charts/ChartRenderer'

export default function DashboardPage() {
  const navigate = useNavigate()
  const { id: routeDashboardId } = useParams()
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const [dashboards, setDashboards] = useState<Dashboard[]>([])
  const [activeDashboard, setActiveDashboard] = useState<DashboardDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [refreshing, setRefreshing] = useState<string | null>(null)

  useEffect(() => {
    if (routeDashboardId) {
      handleSelect(routeDashboardId)
    } else {
      loadDashboards()
    }
  }, [routeDashboardId])

  const loadDashboards = async () => {
    setLoading(true)
    try {
      const list = await dashboardsApi.list(user?.id || 'anonymous')
      setDashboards(list)
    } catch {
      setDashboards([])
    }
    setLoading(false)
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await dashboardsApi.create({ name: newName, description: newDesc, owner_id: user?.id })
      setShowCreateModal(false)
      setNewName('')
      setNewDesc('')
      loadDashboards()
    } catch {}
  }

  const handleSelect = async (id: string) => {
    try {
      const detail = await dashboardsApi.get(id)
      setActiveDashboard(detail)
    } catch {}
  }

  const handleDelete = async (id: string) => {
    try {
      await dashboardsApi.delete(id)
      if (activeDashboard?.id === id) setActiveDashboard(null)
      loadDashboards()
    } catch {}
  }

  const handleRefresh = async (chartId: string) => {
    if (!activeDashboard) return
    setRefreshing(chartId)
    try {
      const result = await dashboardsApi.refreshChart(activeDashboard.id, chartId)
      const updatedCharts = activeDashboard.charts.map(c =>
        c.id === chartId ? { ...c, viz_config: result.viz_config } : c
      )
      setActiveDashboard({ ...activeDashboard, charts: updatedCharts })
    } catch {}
    setRefreshing(null)
  }

  const renderChart = (chart: DashboardChart) => {
    return (
      <div
        key={chart.id}
        className={`group relative rounded-xl border overflow-hidden ${
          theme === 'dark' ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-slate-200'
        }`}
      >
        {/* Chart Header */}
        <div className={`flex items-center justify-between px-4 py-2.5 border-b ${
          theme === 'dark' ? 'border-zinc-800' : 'border-slate-100'
        }`}>
          <div className="flex items-center gap-2">
            <BarChart3 size={14} className={theme === 'dark' ? 'text-zinc-400' : 'text-slate-400'} />
            <span className={`text-xs font-medium ${theme === 'dark' ? 'text-zinc-200' : 'text-slate-700'}`}>
              {chart.title}
            </span>
          </div>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
            <button
              onClick={() => handleRefresh(chart.id)}
              disabled={refreshing === chart.id}
              className={`p-1.5 rounded-lg transition ${
                theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-400' : 'hover:bg-slate-100 text-slate-500'
              }`}
              title="Refresh"
            >
              <RefreshCw size={13} className={refreshing === chart.id ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={async () => {
                if (!activeDashboard) return
                try {
                  await dashboardsApi.deleteChart(activeDashboard.id, chart.id)
                  setActiveDashboard({
                    ...activeDashboard,
                    charts: activeDashboard.charts.filter(c => c.id !== chart.id)
                  })
                } catch {}
              }}
              className={`p-1.5 rounded-lg transition ${
                theme === 'dark' ? 'hover:bg-red-900/20 text-zinc-400 hover:text-red-400' : 'hover:bg-red-50 text-slate-500 hover:text-red-500'
              }`}
              title="Remove"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
        {/* Chart Body */}
        <div className="p-3">
          {chart.viz_config ? (
            <div className="h-64">
              <ChartRenderer vizConfig={chart.viz_config} vizType={null} theme={theme} />
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center">
              <div className={`flex flex-col items-center gap-2 ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                <Table size={24} />
                <span className="text-xs">No visualization config</span>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={`flex h-screen ${theme === 'dark' ? 'bg-zinc-950' : 'bg-slate-50'}`}>
      <div className="flex flex-col flex-1">
        {/* Header */}
        <header className={`flex items-center justify-between px-6 py-4 border-b shadow-sm z-10 ${
          theme === 'dark' ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-slate-200'
        }`}>
          <div className="flex items-center gap-3">
            {activeDashboard ? (
              <button
                onClick={() => setActiveDashboard(null)}
                className={`p-2 rounded-lg transition-colors ${
                  theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-slate-100 text-slate-600'
                }`}
              >
                <ChevronLeft size={18} />
              </button>
            ) : null}
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <LayoutDashboard size={18} className="text-white" />
            </div>
            <div>
              <h1 className={`font-semibold text-sm ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>
                {activeDashboard ? activeDashboard.name : 'Dashboards'}
              </h1>
              <p className={`text-xs ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-400'}`}>
                {activeDashboard ? `${activeDashboard.charts.length} charts` : 'Visual analytics workspace'}
              </p>
            </div>
          </div>
          {!activeDashboard && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium rounded-lg transition shadow-sm"
            >
              <Plus size={14} /> New Dashboard
            </button>
          )}
        </header>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {!activeDashboard ? (
            <>
              {loading ? (
                <div className={`text-center py-20 ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                  Loading...
                </div>
              ) : dashboards.length === 0 ? (
                <div className={`flex flex-col items-center justify-center py-20 ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                  <LayoutDashboard size={48} className="mb-4 opacity-30" />
                  <p className="text-sm font-medium mb-1">No dashboards yet</p>
                  <p className="text-xs mb-4">Create your first dashboard to get started</p>
                  <button
                    onClick={() => setShowCreateModal(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium rounded-lg transition"
                  >
                    <Plus size={14} /> Create Dashboard
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {dashboards.map(d => (
                    <button
                      key={d.id}
                      onClick={() => handleSelect(d.id)}
                      className={`group relative p-5 rounded-xl border text-left transition hover:shadow-md ${
                        theme === 'dark' ? 'bg-zinc-900 border-zinc-800 hover:border-zinc-700' : 'bg-white border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                          <LayoutDashboard size={18} className="text-white" />
                        </div>
                        <button
                          onClick={e => { e.stopPropagation(); handleDelete(d.id) }}
                          className={`p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition ${
                            theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-400 hover:text-red-400' : 'hover:bg-slate-100 text-slate-400 hover:text-red-500'
                          }`}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                      <h3 className={`font-medium text-sm mb-1 ${theme === 'dark' ? 'text-zinc-200' : 'text-slate-800'}`}>
                        {d.name}
                      </h3>
                      {d.description && (
                        <p className={`text-xs mb-3 line-clamp-2 ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                          {d.description}
                        </p>
                      )}
                      <div className={`flex items-center gap-3 text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                        <span>{d.chart_count} charts</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {activeDashboard.charts.map(renderChart)}
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100]">
          <div className={`${theme === 'dark' ? 'bg-zinc-900 border-zinc-700' : 'bg-white border-slate-200'} border rounded-2xl shadow-xl max-w-md w-full mx-4 p-5`}>
            <h3 className={`font-bold text-base mb-4 ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>
              New Dashboard
            </h3>
            <div className="space-y-3">
              <input
                type="text" placeholder="Dashboard name" value={newName}
                onChange={e => setNewName(e.target.value)}
                className={`w-full px-3 py-2 rounded-lg border text-sm outline-none ${
                  theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-500' : 'bg-white border-slate-200 text-slate-900 placeholder:text-slate-400'
                }`}
              />
              <input
                type="text" placeholder="Description (optional)" value={newDesc}
                onChange={e => setNewDesc(e.target.value)}
                className={`w-full px-3 py-2 rounded-lg border text-sm outline-none ${
                  theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-500' : 'bg-white border-slate-200 text-slate-900 placeholder:text-slate-400'
                }`}
              />
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button
                onClick={() => setShowCreateModal(false)}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium ${
                  theme === 'dark' ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
