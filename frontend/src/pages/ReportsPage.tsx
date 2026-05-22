import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Plus, ChevronLeft, Download, Trash2, Clock } from 'lucide-react'
import { useThemeStore } from '../store/theme'
import { reportsApi, type Report } from '../api/reports'
import { format } from 'date-fns'

export default function ReportsPage() {
  const navigate = useNavigate()
  const { theme } = useThemeStore()
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [exporting, setExporting] = useState<string | null>(null)

  useEffect(() => {
    loadReports()
  }, [])

  const loadReports = async () => {
    setLoading(true)
    try {
      const list = await reportsApi.list()
      setReports(list)
    } catch {
      setReports([])
    }
    setLoading(false)
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      await reportsApi.create({ name: newName })
      setShowCreateModal(false)
      setNewName('')
      loadReports()
    } catch {}
  }

  const handleDelete = async (id: string) => {
    try {
      await reportsApi.delete(id)
      loadReports()
    } catch {}
  }

  const handleExport = async (id: string) => {
    setExporting(id)
    try {
      const result = await reportsApi.exportReport(id)
      const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${result.name || 'report'}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch {}
    setExporting(null)
  }

  return (
    <div className={`flex h-screen ${theme === 'dark' ? 'bg-zinc-950' : 'bg-slate-50'}`}>
      <div className="flex flex-col flex-1">
        {/* Header */}
        <header className={`flex items-center justify-between px-6 py-4 border-b shadow-sm z-10 ${
          theme === 'dark' ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-slate-200'
        }`}>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className={`p-2 rounded-lg transition-colors ${
                theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-slate-100 text-slate-600'
              }`}
            >
              <ChevronLeft size={18} />
            </button>
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center">
              <FileText size={18} className="text-white" />
            </div>
            <div>
              <h1 className={`font-semibold text-sm ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>
                Reports
              </h1>
              <p className={`text-xs ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-400'}`}>
                Scheduled & exported reports
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-orange-600 hover:bg-orange-700 text-white text-xs font-medium rounded-lg transition shadow-sm"
          >
            <Plus size={14} /> New Report
          </button>
        </header>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className={`text-center py-20 ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>Loading...</div>
          ) : reports.length === 0 ? (
            <div className={`flex flex-col items-center justify-center py-20 ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
              <FileText size={48} className="mb-4 opacity-30" />
              <p className="text-sm font-medium mb-1">No reports yet</p>
              <p className="text-xs mb-4">Generate reports from your conversations and dashboards</p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white text-xs font-medium rounded-lg transition"
              >
                <Plus size={14} /> Create Report
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {reports.map(r => (
                <div
                  key={r.id}
                  className={`group p-5 rounded-xl border ${
                    theme === 'dark' ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-slate-200'
                  }`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center">
                      <FileText size={18} className="text-white" />
                    </div>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition">
                      <button
                        onClick={() => handleExport(r.id)}
                        disabled={exporting === r.id}
                        className={`p-1.5 rounded-lg ${
                          theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-400 hover:text-blue-400' : 'hover:bg-slate-100 text-slate-400 hover:text-blue-500'
                        }`}
                        title="Export"
                      >
                        <Download size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(r.id)}
                        className={`p-1.5 rounded-lg ${
                          theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-400 hover:text-red-400' : 'hover:bg-slate-100 text-slate-400 hover:text-red-500'
                        }`}
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <h3 className={`font-medium text-sm mb-1 ${theme === 'dark' ? 'text-zinc-200' : 'text-slate-800'}`}>
                    {r.name}
                  </h3>
                  <div className={`flex items-center gap-3 text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                    <span className="flex items-center gap-1">
                      <Clock size={12} />
                      {format(new Date(r.created_at), 'MMM d, yyyy')}
                    </span>
                    <span className="uppercase">{r.format}</span>
                    {r.schedule && <span className="text-green-500">Scheduled</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100]">
          <div className={`${theme === 'dark' ? 'bg-zinc-900 border-zinc-700' : 'bg-white border-slate-200'} border rounded-2xl shadow-xl max-w-md w-full mx-4 p-5`}>
            <h3 className={`font-bold text-base mb-4 ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>
              New Report
            </h3>
            <input
              type="text" placeholder="Report name" value={newName}
              onChange={e => setNewName(e.target.value)}
              className={`w-full px-3 py-2 rounded-lg border text-sm outline-none ${
                theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-500' : 'bg-white border-slate-200 text-slate-900 placeholder:text-slate-400'
              }`}
            />
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
                className="px-3 py-1.5 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-xs font-medium"
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
