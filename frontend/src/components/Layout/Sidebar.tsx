import { useState, useEffect } from 'react'
import { X, ChevronLeft, ChevronRight, Pin, PinOff, Settings, User, LogOut, Moon, Sun, Shield, BarChart3 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useChatStore, ChatSession } from '../../store/chat'
import { useAuthStore } from '../../store/auth'
import { useThemeStore } from '../../store/theme'
import { logout } from '../../api/auth'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
}

export default function Sidebar({ isOpen, onToggle }: SidebarProps) {
  const { sessions, activeSessionId, loadSession, startNewSession, deleteSession, togglePin, getPinnedSessions } = useChatStore()
  const { user, clearAuth } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const navigate = useNavigate()

  const [showSettings, setShowSettings] = useState(false)

  const pinnedSessions = getPinnedSessions()
  const unpinnedSessions = sessions.filter(s => !s.pinned)

  const handleLogout = async () => {
    await logout()
    clearAuth()
    navigate('/login')
  }

  const width = isOpen ? '240px' : '56px'

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full bg-zinc-950 text-white flex flex-col transition-all duration-300 z-50 ${
          isOpen ? 'w-60' : 'w-14'
        }`}
        style={{ width: isOpen ? '240px' : '56px' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-zinc-800">
          {isOpen && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <span className="text-white text-sm font-bold">AC</span>
              </div>
              <span className="font-semibold text-sm">Analytics Copilot</span>
            </div>
          )}
          <button
            onClick={onToggle}
            className="p-1.5 hover:bg-zinc-800 rounded-lg transition-colors ml-auto"
          >
            {isOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-2">
          <button
            onClick={startNewSession}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
              isOpen
                ? 'bg-blue-600 hover:bg-blue-700 text-white justify-start'
                : 'bg-blue-600 hover:bg-blue-700 text-white justify-center'
            }`}
          >
            <span className="text-lg font-light">+</span>
            {isOpen && <span className="text-sm">New Chat</span>}
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-4">
          {/* Pinned Conversations */}
          {pinnedSessions.length > 0 && (
            <div>
              {isOpen && (
                <p className="px-2 py-1 text-xs text-zinc-500 font-medium">Pinned</p>
              )}
              <div className="space-y-1">
                {pinnedSessions.map(session => (
                  <SidebarSessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeSessionId}
                    isExpanded={isOpen}
                    onSelect={() => loadSession(session.id)}
                    onTogglePin={() => togglePin(session.id)}
                    onDelete={() => deleteSession(session.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Recent Conversations */}
          {unpinnedSessions.length > 0 && (
            <div>
              {isOpen && (
                <p className="px-2 py-1 text-xs text-zinc-500 font-medium">Recent</p>
              )}
              <div className="space-y-1">
                {unpinnedSessions.slice(0, 10).map(session => (
                  <SidebarSessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeSessionId}
                    isExpanded={isOpen}
                    onSelect={() => loadSession(session.id)}
                    onTogglePin={() => togglePin(session.id)}
                    onDelete={() => deleteSession(session.id)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-2 border-t border-zinc-800 space-y-1">
          {/* Analytics link - all users */}
          <button
            onClick={() => navigate('/analytics')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors ${
              isOpen ? 'justify-start' : 'justify-center'
            }`}
            title="Your analytics"
          >
            <BarChart3 size={16} className="text-blue-400" />
            {isOpen && <span className="text-sm">Analytics</span>}
          </button>

          {/* Admin link - admin/business_analyst only */}
          {(user?.role === 'admin' || user?.role === 'business_analyst') && (
            <button
              onClick={() => navigate('/admin')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors ${
                isOpen ? 'justify-start' : 'justify-center'
              }`}
              title="Admin panel"
            >
              <Shield size={16} className="text-purple-400" />
              {isOpen && <span className="text-sm">Admin</span>}
            </button>
          )}

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors ${
              isOpen ? 'justify-start' : 'justify-center'
            }`}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? (
              <Sun size={16} className="text-yellow-400" />
            ) : (
              <Moon size={16} className="text-zinc-400" />
            )}
            {isOpen && <span className="text-sm">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
          </button>

          {/* Settings */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-800 transition-colors ${
              isOpen ? 'justify-start' : 'justify-center'
            }`}
          >
            <Settings size={16} className="text-zinc-400" />
            {isOpen && <span className="text-sm">Settings</span>}
          </button>

          {/* User Profile & Logout */}
          {isOpen && user && (
            <div className="px-3 py-2">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <span className="text-white text-xs font-medium">
                    {user.name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{user.name}</p>
                  <p className="text-xs text-zinc-500 truncate">{user.email}</p>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-zinc-800 transition-colors text-sm text-zinc-400 hover:text-white"
              >
                <LogOut size={14} />
                <span>Logout</span>
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  )
}

interface SidebarSessionItemProps {
  session: ChatSession
  isActive: boolean
  isExpanded: boolean
  onSelect: () => void
  onTogglePin: () => void
  onDelete: () => void
}

function SidebarSessionItem({
  session,
  isActive,
  isExpanded,
  onSelect,
  onTogglePin,
  onDelete,
}: SidebarSessionItemProps) {
  const [showActions, setShowActions] = useState(false)

  return (
    <div
      className={`group relative flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors ${
        isActive ? 'bg-zinc-800' : 'hover:bg-zinc-800/50'
      }`}
      onMouseEnter={() => isExpanded && setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <button
        onClick={onSelect}
        className={`flex-1 flex items-center gap-2 min-w-0 ${
          isExpanded ? 'justify-start' : 'justify-center'
        }`}
      >
        {session.pinned ? (
          <Pin size={14} className="text-blue-400 flex-shrink-0" />
        ) : (
          <div className="w-3.5 h-3.5 rounded-full bg-zinc-700 flex-shrink-0" />
        )}
        {isExpanded && (
          <span className="text-sm text-zinc-300 truncate">{session.title}</span>
        )}
      </button>

      {/* Actions - shown on hover when expanded */}
      {isExpanded && showActions && (
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onTogglePin()
            }}
            className="p-1 hover:bg-zinc-700 rounded transition-colors"
            title={session.pinned ? 'Unpin' : 'Pin'}
          >
            {session.pinned ? (
              <PinOff size={12} className="text-zinc-400" />
            ) : (
              <Pin size={12} className="text-zinc-400" />
            )}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className="p-1 hover:bg-zinc-700 rounded transition-colors"
            title="Delete"
          >
            <X size={12} className="text-zinc-400 hover:text-red-400" />
          </button>
        </div>
      )}
    </div>
  )
}
