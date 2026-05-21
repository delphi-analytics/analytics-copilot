import { ChevronDown, ChevronRight, CheckCircle2, Loader2, Database, Code, BarChart3, Lightbulb } from 'lucide-react'
import { useState } from 'react'
import { useThemeStore } from '../store/theme'
import type { TransparencyStep } from '../hooks/useStreamingQuery'

interface TransparencyPanelProps {
  steps: TransparencyStep[]
  isComplete: boolean
  sql?: string
  tables?: string[]
  columns?: string[]
}

// Step icons for visual clarity
const STEP_ICONS: Record<string, React.ReactNode> = {
  understand_intent: <Lightbulb size={14} />,
  discover_schema: <Database size={14} />,
  generate_sql: <Code size={14} />,
  execute_sql: <Database size={14} />,
  analyze_insights: <Lightbulb size={14} />,
  generate_viz_config: <BarChart3 size={14} />,
  compose_response: <CheckCircle2 size={14} />,
}

export default function TransparencyPanel({
  steps,
  isComplete,
  sql,
  tables,
  columns,
}: TransparencyPanelProps) {
  const { theme } = useThemeStore()
  const [isExpanded, setIsExpanded] = useState(true)

  // Extract current step and progress info
  const lastStep = steps[steps.length - 1]
  const currentStep = lastStep?.step || lastStep?.message || ''
  const isWorking = !isComplete && steps.length > 0

  // Calculate overall progress percentage
  const progressPercent = lastStep?.progress || 0

  // Get final data from complete state
  const finalStep = steps.find(s => s.type === 'complete')

  return (
    <div
      className={`mx-4 mb-2 border rounded-lg overflow-hidden transition-all ${
        theme === 'dark'
          ? 'bg-zinc-900/50 border-zinc-800'
          : 'bg-slate-50 border-slate-200'
      }`}
    >
      {/* Toggle Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`w-full flex items-center justify-between px-3 py-2.5 text-left transition-colors ${
          theme === 'dark' ? 'hover:bg-zinc-800/50' : 'hover:bg-slate-100'
        }`}
      >
        <div className="flex items-center gap-2 text-sm">
          {isWorking ? (
            <Loader2 size={14} className="animate-spin text-blue-500" />
          ) : (
            <CheckCircle2 size={14} className="text-green-500" />
          )}
          <span className={theme === 'dark' ? 'text-zinc-300' : 'text-slate-700'}>
            {isWorking ? 'Processing...' : 'Complete'}
          </span>
          {currentStep && (
            <span className={theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}>
              — {currentStep}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isWorking && (
            <span className={`text-xs font-mono ${theme === 'dark' ? 'text-blue-400' : 'text-blue-600'}`}>
              {progressPercent}%
            </span>
          )}
          {isExpanded ? (
            <ChevronDown size={14} className={theme === 'dark' ? 'text-zinc-400' : 'text-slate-400'} />
          ) : (
            <ChevronRight size={14} className={theme === 'dark' ? 'text-zinc-400' : 'text-slate-400'} />
          )}
        </div>
      </button>

      {/* Progress Bar */}
      {isWorking && (
        <div className="px-3 pb-2">
          <div className={`h-1 rounded-full overflow-hidden ${theme === 'dark' ? 'bg-zinc-800' : 'bg-slate-200'}`}>
            <div
              className="h-full bg-blue-500 transition-all duration-300 ease-out"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Expanded Content */}
      {isExpanded && (
        <div className={`px-3 pb-3 border-t ${theme === 'dark' ? 'border-zinc-800' : 'border-slate-200'}`}>
          {/* Steps List */}
          <div className="space-y-1.5 mt-2">
            {steps.map((step, idx) => (
              <div key={idx} className={`flex items-start gap-2 text-xs ${
                step.type === 'error' ? 'text-red-500' : ''
              }`}>
                <span className={`mt-0.5 ${
                  step.type === 'complete' ? 'text-green-500' :
                  step.type === 'error' ? 'text-red-500' :
                  theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'
                }`}>
                  {step.type === 'complete' ? '✓' :
                   step.type === 'error' ? '✗' :
                   step.type === 'progress' ? (STEP_ICONS[step.step || ''] || '→') : '→'}
                </span>
                <div className="flex-1">
                  <div className={`font-medium ${theme === 'dark' ? 'text-zinc-300' : 'text-slate-600'}`}>
                    {step.message || step.step}
                  </div>

                  {/* Partial results for each step */}
                  {step.data && Object.keys(step.data).length > 0 && (
                    <div className="mt-1 space-y-1">
                      {/* Intent */}
                      {step.data.intent && (
                        <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                          theme === 'dark'
                            ? 'bg-purple-900/30 text-purple-300'
                            : 'bg-purple-100 text-purple-700'
                        }`}>
                          Intent: {step.data.intent}
                        </span>
                      )}

                      {/* Row count */}
                      {step.data.row_count !== undefined && (
                        <span className={`inline-block px-2 py-0.5 rounded text-xs ml-1 ${
                          theme === 'dark'
                            ? 'bg-green-900/30 text-green-300'
                            : 'bg-green-100 text-green-700'
                        }`}>
                          {step.data.row_count.toLocaleString()} rows
                        </span>
                      )}

                      {/* Preview of columns */}
                      {step.data.columns && step.data.columns.length > 0 && (
                        <div className={`flex flex-wrap gap-1 mt-1`}>
                          {step.data.columns.slice(0, 5).map(col => (
                            <span
                              key={col}
                              className={`px-1.5 py-0.5 rounded text-xs font-mono ${
                                theme === 'dark'
                                  ? 'bg-zinc-800 text-zinc-400'
                                  : 'bg-slate-100 text-slate-600'
                              }`}
                            >
                              {col}
                            </span>
                          ))}
                          {step.data.columns.length > 5 && (
                            <span className={`text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                              +{step.data.columns.length - 5} more
                            </span>
                          )}
                        </div>
                      )}

                      {/* Preview of insights */}
                      {step.data.insights && step.data.insights.length > 0 && (
                        <div className={`mt-1 p-2 rounded text-xs ${
                          theme === 'dark'
                            ? 'bg-amber-900/20 text-amber-300'
                            : 'bg-amber-50 text-amber-800'
                        }`}>
                          <strong>Insights:</strong> {step.data.insights[0]}
                          {step.data.insights.length > 1 && (
                            <span className={theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}>
                              {' '}+{step.data.insights.length - 1} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Final Details */}
          {isComplete && (sql || tables || columns) && (
            <div className={`mt-3 pt-3 border-t ${theme === 'dark' ? 'border-zinc-800' : 'border-slate-200'}`}>
              {/* Tables Used */}
              {tables && tables.length > 0 && (
                <div className="mb-2">
                  <span className={`text-xs font-medium ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>
                    Tables:
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {tables.map(table => (
                      <span
                        key={table}
                        className={`px-2 py-0.5 rounded text-xs font-mono ${
                          theme === 'dark'
                            ? 'bg-blue-900/30 text-blue-300'
                            : 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {table}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Columns Used */}
              {columns && columns.length > 0 && (
                <div className="mb-2">
                  <span className={`text-xs font-medium ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>
                    Columns:
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {columns.slice(0, 10).map(column => (
                      <span
                        key={column}
                        className={`px-2 py-0.5 rounded text-xs font-mono ${
                          theme === 'dark'
                            ? 'bg-purple-900/30 text-purple-300'
                            : 'bg-purple-100 text-purple-700'
                        }`}
                      >
                        {column}
                      </span>
                    ))}
                    {columns.length > 10 && (
                      <span className={`text-xs ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>
                        +{columns.length - 10} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* SQL Query */}
              {sql && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-medium ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>
                      SQL Query:
                    </span>
                    <button
                      onClick={() => navigator.clipboard.writeText(sql)}
                      className={`text-xs hover:underline ${
                        theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
                      }`}
                    >
                      Copy
                    </button>
                  </div>
                  <pre
                    className={`p-2 rounded text-xs font-mono overflow-x-auto ${
                      theme === 'dark'
                        ? 'bg-zinc-950 text-zinc-300'
                        : 'bg-white text-slate-700 border border-slate-200'
                    }`}
                  >
                    {sql}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
