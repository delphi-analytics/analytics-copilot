import { AlertCircle } from 'lucide-react'

interface DisambiguationModalProps {
  keyword: string
  options: string[]
  onSelect: (selected: string) => void
  onDismiss: () => void
}

export default function DisambiguationModal({
  keyword,
  options,
  onSelect,
  onDismiss,
}: DisambiguationModalProps) {
  return (
    <div className="mx-4 mb-4 p-4 bg-amber-50 dark:bg-zinc-amber-900/20 border border-amber-200 dark:border-zinc-amber-800 rounded-lg">
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-amber-600 dark:text-zinc-amber-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm text-amber-900 dark:text-zinc-amber-100 font-medium mb-1">
            Clarification needed: What do you mean by "{keyword}"?
          </p>
          <p className="text-xs text-amber-700 dark:text-zinc-amber-300 mb-3">
            Please select the intended meaning to continue:
          </p>
          <div className="flex flex-wrap gap-2">
            {options.map((option) => (
              <button
                key={option}
                onClick={() => onSelect(option)}
                className="px-3 py-1.5 bg-white dark:bg-zinc-slate-800 border border-amber-300 dark:border-zinc-amber-700 rounded-md text-sm text-amber-900 dark:text-zinc-amber-100 hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors"
              >
                {option}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="text-amber-600 dark:text-zinc-amber-400 hover:text-amber-800 dark:hover:text-amber-200"
        >
          ×
        </button>
      </div>
    </div>
  )
}
