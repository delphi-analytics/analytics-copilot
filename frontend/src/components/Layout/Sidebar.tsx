import { useState, useEffect } from 'react'
import {
  X, ChevronLeft, ChevronRight, Pin, PinOff, Settings, User, LogOut, Moon, Sun,
  Shield, Search, MessageSquare, Grid3X3, HelpCircle, UserCircle, Sparkles,
  LayoutDashboard, FileText, BarChart3
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useChatStore, ChatSession } from '../../store/chat'
import { useAuthStore } from '../../store/auth'
import { useThemeStore } from '../../store/theme'
import { logout } from '../../api/auth'
import { getDatasources } from '../../api/client'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
}

export default function Sidebar({ isOpen, onToggle }: SidebarProps) {
  const {
    sessions, activeSessionId, loadSession, startNewSession, deleteSession,
    togglePin, getPinnedSessions, datasourceId, setDatasourceId
  } = useChatStore()
  const { user, clearAuth, updateUser } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const navigate = useNavigate()

  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [datasources, setDatasources] = useState<any[]>([])

  useEffect(() => {
    if (showSettings) {
      getDatasources()
        .then(setDatasources)
        .catch(err => console.error("Failed to load datasources", err))
    }
  }, [showSettings])


  const pinnedSessions = getPinnedSessions()
  const unpinnedSessions = sessions.filter(s => !s.pinned)

  // Filter sessions based on search
  const filteredSessions = unpinnedSessions.filter(s =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const handleLogout = async () => {
    await logout()
    clearAuth()
    navigate('/login')
  }

  const handleLogoutClick = () => {
    setShowUserMenu(false)
    setShowLogoutConfirm(true)
  }

  const width = isOpen ? '240px' : '56px'

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setShowUserMenu(false)
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  return (
    <>
      {/* Logout Confirmation Modal */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className={`${theme === 'dark' ? 'bg-zinc-800' : 'bg-white'} rounded-xl p-6 max-w-sm w-full shadow-2xl`}>
            <h3 className={`text-lg font-semibold mb-2 ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>
              Confirm Logout
            </h3>
            <p className={`text-sm mb-6 ${theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'}`}>
              Are you sure you want to log out? Your chat history will be saved for your next session.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className={`flex-1 px-4 py-2 rounded-lg font-medium transition-colors ${
                  theme === 'dark'
                    ? 'bg-zinc-700 text-white hover:bg-zinc-600'
                    : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'
                }`}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowLogoutConfirm(false)
                  handleLogout()
                }}
                className="flex-1 px-4 py-2 rounded-lg font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className={`${theme === 'dark' ? 'bg-zinc-800' : 'bg-white'} rounded-xl p-6 max-w-md w-full shadow-2xl`}>
            <div className="flex items-center justify-between mb-6">
              <h3 className={`text-lg font-semibold ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>
                Settings
              </h3>
              <button
                onClick={() => setShowSettings(false)}
                className={`p-1 rounded-lg ${theme === 'dark' ? 'hover:bg-zinc-700' : 'hover:bg-zinc-100'}`}
              >
                <X size={20} className={theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'} />
              </button>
            </div>

            <div className="space-y-4">
              <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-zinc-700' : 'bg-zinc-50'}`}>
                <h4 className={`font-medium mb-1 ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>
                  Theme
                </h4>
                <p className={`text-sm ${theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'}`}>
                  Current: {theme === 'dark' ? 'Dark Mode' : 'Light Mode'}
                </p>
              </div>

              <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-zinc-700' : 'bg-zinc-50'}`}>
                <h4 className={`font-medium mb-1 ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>
                  Datasource
                </h4>
                {datasources.length === 0 ? (
                  <p className={`text-sm ${theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'}`}>
                    Loading datasources...
                  </p>
                ) : (
                  <select
                    value={datasourceId}
                    onChange={(e) => {
                      setDatasourceId(e.target.value)
                      startNewSession()
                    }}
                    className={`w-full p-2 text-sm rounded border ${
                      theme === 'dark'
                        ? 'bg-zinc-800 border-zinc-600 text-white'
                        : 'bg-white border-zinc-200 text-zinc-900'
                    } outline-none focus:ring-1 focus:ring-blue-500`}
                  >
                    {datasources.map((ds) => (
                      <option key={ds.id} value={ds.id}>
                        {ds.id === 'default' ? 'SQLite Demo' : ds.id === 'limese' ? 'Limese ClickHouse' : `${ds.id} (${ds.type})`}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className={`p-4 rounded-lg ${theme === 'dark' ? 'bg-zinc-700' : 'bg-zinc-50'}`}>
                <h4 className={`font-medium mb-1 ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>
                  Account & Role
                </h4>
                <p className={`text-sm mb-2 ${theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'}`}>
                  {user?.name} ({user?.email})
                </p>
                <label className={`block text-[10px] font-semibold uppercase tracking-wider mb-1 ${theme === 'dark' ? 'text-zinc-400' : 'text-zinc-500'}`}>
                  Select User Role
                </label>
                <select
                  value={user?.role || 'team_member'}
                  onChange={(e) => updateUser({ role: e.target.value })}
                  className={`w-full p-2 text-sm rounded border ${
                    theme === 'dark'
                      ? 'bg-zinc-800 border-zinc-600 text-white'
                      : 'bg-white border-zinc-200 text-zinc-900'
                  } outline-none focus:ring-1 focus:ring-blue-500`}
                >
                  <option value="business_analyst">Business Analyst</option>
                  <option value="team_member">Team Member</option>
                  <option value="non_tech_user">Non-tech User</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full flex flex-col transition-all duration-300 z-50 ${
          theme === 'dark' ? 'bg-zinc-950 text-white' : 'bg-slate-50 text-zinc-900 border-r border-slate-200'
        } ${isOpen ? 'w-60' : 'w-14'}`}
        style={{ width: isOpen ? '240px' : '56px' }}
      >
        {/* Header */}
        <div className={`flex items-center justify-between p-3 ${theme === 'dark' ? 'border-zinc-800' : 'border-slate-200'} border-b`}>
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
            className={`p-1.5 rounded-lg transition-colors ml-auto ${theme === 'dark' ? 'hover:bg-zinc-800' : 'hover:bg-slate-200'}`}
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
            <MessageSquare size={16} />
            {isOpen && <span className="text-sm">New Chat</span>}
          </button>
        </div>

        {/* Search Chat */}
        {isOpen && (
          <div className="px-2 pb-2">
            <div className={`relative flex items-center gap-2 px-3 py-2 rounded-lg ${
              theme === 'dark' ? 'bg-zinc-900' : 'bg-white border border-slate-200'
            }`}>
              <Search size={16} className={theme === 'dark' ? 'text-zinc-500' : 'text-zinc-400'} />
              <input
                type="text"
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={`flex-1 bg-transparent outline-none text-sm ${
                  theme === 'dark' ? 'text-white placeholder:text-zinc-500' : 'text-zinc-900 placeholder:text-zinc-400'
                }`}
              />
            </div>
          </div>
        )}

        {/* Navigation Links */}
        {isOpen && (
          <div className="px-2 pb-2 space-y-1">
            <button
              onClick={() => navigate('/')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-slate-100 text-slate-600'
              }`}
            >
              <MessageSquare size={16} />
              <span className="text-sm">Chat</span>
            </button>
            <button
              onClick={() => navigate('/dashboards')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-slate-100 text-slate-600'
              }`}
            >
              <LayoutDashboard size={16} />
              <span className="text-sm">Dashboards</span>
            </button>
            <button
              onClick={() => navigate('/reports')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-slate-100 text-slate-600'
              }`}
            >
              <FileText size={16} />
              <span className="text-sm">Reports</span>
            </button>
            <button
              onClick={() => navigate('/analytics')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-slate-100 text-slate-600'
              }`}
            >
              <BarChart3 size={16} />
              <span className="text-sm">Analytics</span>
            </button>
          </div>
        )}
        {/* Divider */}
        {isOpen && <div className={`mx-2 h-px ${theme === 'dark' ? 'bg-zinc-800' : 'bg-slate-200'}`} />}

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-4">
          {/* Pinned Conversations */}
          {pinnedSessions.length > 0 && (
            <div>
              {isOpen && (
                <p className={`px-2 py-1 text-xs font-medium ${theme === 'dark' ? 'text-zinc-500' : 'text-zinc-400'}`}>Pinned</p>
              )}
              <div className="space-y-1">
                {pinnedSessions.map(session => (
                  <SidebarSessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeSessionId}
                    isExpanded={isOpen}
                    theme={theme}
                    onSelect={() => loadSession(session.id)}
                    onTogglePin={() => togglePin(session.id)}
                    onDelete={() => deleteSession(session.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Recent Conversations */}
          {filteredSessions.length > 0 && (
            <div>
              {isOpen && (
                <p className={`px-2 py-1 text-xs font-medium ${theme === 'dark' ? 'text-zinc-500' : 'text-zinc-400'}`}>
                  {searchQuery ? 'Search Results' : 'Recent'}
                </p>
              )}
              <div className="space-y-1">
                {filteredSessions.slice(0, 10).map(session => (
                  <SidebarSessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeSessionId}
                    isExpanded={isOpen}
                    theme={theme}
                    onSelect={() => loadSession(session.id)}
                    onTogglePin={() => togglePin(session.id)}
                    onDelete={() => deleteSession(session.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {searchQuery && filteredSessions.length === 0 && (
            <div className={`text-center py-8 ${theme === 'dark' ? 'text-zinc-500' : 'text-zinc-400'}`}>
              <p className="text-sm">No chats found</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={`p-2 space-y-1 ${theme === 'dark' ? 'border-zinc-800' : 'border-slate-200'} border-t`}>
          {/* Admin link - admin only */}
          {user?.role === 'admin' && (
            <button
              onClick={() => navigate('/admin')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                theme === 'dark' ? 'hover:bg-zinc-800' : 'hover:bg-slate-200'
              } ${isOpen ? 'justify-start' : 'justify-center'}`}
              title="Admin panel"
            >
              <Shield size={16} className="text-purple-400" />
              {isOpen && <span className="text-sm">Admin</span>}
            </button>
          )}

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
              theme === 'dark' ? 'hover:bg-zinc-800' : 'hover:bg-slate-200'
            } ${isOpen ? 'justify-start' : 'justify-center'}`}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? (
              <Sun size={16} className="text-yellow-400" />
            ) : (
              <Moon size={16} className="text-zinc-600" />
            )}
            {isOpen && <span className="text-sm">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
          </button>

          {/* Settings */}
          <button
            onClick={() => navigate('/settings')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
              theme === 'dark' ? 'hover:bg-zinc-800' : 'hover:bg-slate-200'
            } ${isOpen ? 'justify-start' : 'justify-center'}`}
          >
            <Settings size={16} className={theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'} />
            {isOpen && <span className="text-sm">Settings</span>}
          </button>

          {/* User Profile Dropdown */}
          {isOpen && user && (
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setShowUserMenu(!showUserMenu)
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                  theme === 'dark' ? 'hover:bg-zinc-800' : 'hover:bg-slate-200'
                }`}
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <span className="text-white text-xs font-medium">
                    {user.name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
                  </span>
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium truncate">{user.name}</p>
                  <p className={`text-xs truncate ${theme === 'dark' ? 'text-zinc-500' : 'text-zinc-400'}`}>{user.email}</p>
                </div>
                <Grid3X3 size={16} className={theme === 'dark' ? 'text-zinc-500' : 'text-zinc-400'} />
              </button>

              {/* Dropdown Menu */}
              {showUserMenu && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className={`absolute bottom-full left-0 right-0 mb-2 rounded-xl shadow-xl overflow-hidden ${
                    theme === 'dark' ? 'bg-zinc-800 border border-zinc-700' : 'bg-white border border-slate-200'
                  }`}
                >
                  {/* Profile Header */}
                  <div className={`p-4 border-b ${theme === 'dark' ? 'border-zinc-700' : 'border-slate-100'}`}>
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                        <span className="text-white font-medium">
                          {user.name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <div className="flex-1">
                        <p className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>{user.name}</p>
                        <p className={`text-[10px] ${theme === 'dark' ? 'text-zinc-400' : 'text-zinc-500'}`}>
                          Active Role: {user.role === 'admin' ? 'Administrator' :
                           user.role === 'business_analyst' ? 'Business Analyst' :
                           user.role === 'team_member' ? 'Team Member' : 'Non-tech User'}
                        </p>
                      </div>
                      <button className={`p-1 rounded ${theme === 'dark' ? 'hover:bg-zinc-700' : 'hover:bg-slate-100'}`}>
                        <Grid3X3 size={16} className={theme === 'dark' ? 'text-zinc-400' : 'text-zinc-400'} />
                      </button>
                    </div>
                    <div className="mt-3">
                      <label className={`block text-[10px] font-semibold uppercase tracking-wider mb-1 ${theme === 'dark' ? 'text-zinc-400' : 'text-zinc-500'}`}>
                        Role Switcher
                      </label>
                      <select
                        value={user?.role || 'team_member'}
                        onChange={(e) => updateUser({ role: e.target.value })}
                        onClick={(ev) => ev.stopPropagation()}
                        className={`w-full px-2 py-1 text-xs rounded border ${
                          theme === 'dark'
                            ? 'bg-zinc-900 border-zinc-700 text-white'
                            : 'bg-white border-zinc-200 text-zinc-900'
                        } outline-none focus:ring-1 focus:ring-blue-500`}
                      >
                        <option value="business_analyst">Business Analyst</option>
                        <option value="team_member">Team Member</option>
                        <option value="non_tech_user">Non-tech User</option>
                      </select>
                    </div>
                  </div>

                  {/* Menu Options */}
                  <div className="p-2">
                    <button
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                        theme === 'dark' ? 'hover:bg-zinc-700' : 'hover:bg-slate-50'
                      }`}
                    >
                      <Sparkles size={18} className="text-purple-400" />
                      <div className="text-left">
                        <p className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>Personalization</p>
                      </div>
                    </button>

                    <button
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                        theme === 'dark' ? 'hover:bg-zinc-700' : 'hover:bg-slate-50'
                      }`}
                    >
                      <UserCircle size={18} className="text-blue-400" />
                      <div className="text-left">
                        <p className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>Profile</p>
                      </div>
                    </button>

                    <button
                      onClick={() => {
                        setShowUserMenu(false)
                        setShowSettings(true)
                      }}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                        theme === 'dark' ? 'hover:bg-zinc-700' : 'hover:bg-slate-50'
                      }`}
                    >
                      <Settings size={18} className={theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'} />
                      <div className="text-left">
                        <p className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>Settings</p>
                      </div>
                    </button>

                    <button
                      onClick={() => {
                        setShowUserMenu(false)
                        window.open('mailto:ecom@delphianalytics.in?subject=Help Request - Analytics Copilot', '_blank')
                      }}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                        theme === 'dark' ? 'hover:bg-zinc-700' : 'hover:bg-slate-50'
                      }`}
                    >
                      <HelpCircle size={18} className="text-green-400" />
                      <div className="text-left">
                        <p className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>Help</p>
                      </div>
                    </button>

                    <div className={`my-2 h-px ${theme === 'dark' ? 'bg-zinc-700' : 'bg-slate-100'}`} />

                    <button
                      onClick={handleLogoutClick}
                      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                        theme === 'dark' ? 'hover:bg-zinc-700' : 'hover:bg-slate-50'
                      }`}
                    >
                      <LogOut size={18} className="text-red-400" />
                      <div className="text-left">
                        <p className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-zinc-900'}`}>Log out</p>
                      </div>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {!isOpen && user && (
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="w-full flex justify-center p-2"
              title={`${user.name} - ${user.email}`}
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <span className="text-white text-xs font-medium">
                  {user.name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
                </span>
              </div>
            </button>
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
  theme: string
  onSelect: () => void
  onTogglePin: () => void
  onDelete: () => void
}

function SidebarSessionItem({
  session,
  isActive,
  isExpanded,
  theme,
  onSelect,
  onTogglePin,
  onDelete,
}: SidebarSessionItemProps) {
  const [showActions, setShowActions] = useState(false)

  return (
    <div
      className={`group relative flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors ${
        theme === 'dark'
          ? isActive ? 'bg-zinc-800' : 'hover:bg-zinc-800/50'
          : isActive ? 'bg-slate-200' : 'hover:bg-slate-100'
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
          <span className={`text-sm truncate ${theme === 'dark' ? 'text-zinc-300' : 'text-zinc-700'}`}>{session.title}</span>
        )}
      </button>

      {isExpanded && showActions && (
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onTogglePin()
            }}
            className={`p-1 hover:bg-zinc-700 rounded transition-colors ${theme === 'dark' ? '' : 'hover:bg-slate-200'}`}
            title={session.pinned ? 'Unpin' : 'Pin'}
          >
            {session.pinned ? (
              <PinOff size={12} className={theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'} />
            ) : (
              <Pin size={12} className={theme === 'dark' ? 'text-zinc-400' : 'text-zinc-600'} />
            )}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className={`p-1 hover:bg-zinc-700 rounded transition-colors ${theme === 'dark' ? '' : 'hover:bg-slate-200'}`}
            title="Delete"
          >
            <X size={12} className={theme === 'dark' ? 'text-zinc-400 hover:text-red-400' : 'text-zinc-600 hover:text-red-400'} />
          </button>
        </div>
      )}
    </div>
  )
}
