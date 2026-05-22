import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  User, Palette, Sparkles, Bell, Shield, ChevronLeft, Save, Eye, EyeOff,
  Check, X, Moon, Sun, Monitor
} from 'lucide-react'
import { useThemeStore } from '../store/theme'
import { useAuthStore } from '../store/auth'
import { settingsApi } from '../api/settings'

type SettingsTab = 'profile' | 'appearance' | 'ai-preferences' | 'notifications'

const tabs: { id: SettingsTab; label: string; icon: React.ReactNode }[] = [
  { id: 'profile', label: 'Profile', icon: <User size={16} /> },
  { id: 'appearance', label: 'Appearance', icon: <Palette size={16} /> },
  { id: 'ai-preferences', label: 'AI Preferences', icon: <Sparkles size={16} /> },
  { id: 'notifications', label: 'Notifications', icon: <Bell size={16} /> },
]

export default function SettingsPage() {
  const navigate = useNavigate()
  const { theme } = useThemeStore()
  const { user, updateUser } = useAuthStore()
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile')
  const [saved, setSaved] = useState(false)

  // Profile state
  const [name, setName] = useState(user?.name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState('')

  // Appearance state
  const { theme: currentTheme, setTheme } = useThemeStore()
  const [compactMode, setCompactMode] = useState(false)
  const [animations, setAnimations] = useState(true)

  // AI Preferences
  const [savedPrompts, setSavedPrompts] = useState<string[]>([])
  const [newPrompt, setNewPrompt] = useState('')
  const [preferredChart, setPreferredChart] = useState('auto')
  const [responseLength, setResponseLength] = useState('balanced')
  const [customInstructions, setCustomInstructions] = useState('')

  // Notifications
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [pushNotifications, setPushNotifications] = useState(false)
  const [weeklyDigest, setWeeklyDigest] = useState(false)

  useEffect(() => {
    setName(user?.name || '')
    setEmail(user?.email || '')
  }, [user])

  useEffect(() => {
    if (saved) {
      const t = setTimeout(() => setSaved(false), 2000)
      return () => clearTimeout(t)
    }
  }, [saved])

  const handleSaveProfile = async () => {
    try {
      await settingsApi.updateProfile({ name, email })
      updateUser({ name, email })
      setSaved(true)
    } catch {
      setSaved(false)
    }
  }

  const handleChangePassword = async () => {
    setPasswordError('')
    setPasswordSuccess('')
    if (!currentPassword || !newPassword) {
      setPasswordError('Both fields are required')
      return
    }
    if (newPassword.length < 6) {
      setPasswordError('New password must be at least 6 characters')
      return
    }
    try {
      await settingsApi.updatePassword({ current_password: currentPassword, new_password: newPassword })
      setPasswordSuccess('Password changed successfully')
      setCurrentPassword('')
      setNewPassword('')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setPasswordError(err?.response?.data?.detail || 'Failed to change password')
    }
  }

  const handleSavePreferences = async () => {
    await settingsApi.updatePreferences({
      preferred_chart: preferredChart,
      response_length: responseLength,
      custom_instructions: customInstructions,
      compact_mode: compactMode,
      animations,
      email_notifications: emailNotifications,
      push_notifications: pushNotifications,
      weekly_digest: weeklyDigest,
    })
    setSaved(true)
  }

  const handleAddPrompt = () => {
    const p = newPrompt.trim()
    if (p && !savedPrompts.includes(p)) {
      setSavedPrompts([...savedPrompts, p])
      setNewPrompt('')
    }
  }

  const handleRemovePrompt = (prompt: string) => {
    setSavedPrompts(savedPrompts.filter(p => p !== prompt))
  }

  return (
    <div className={`flex h-screen ${theme === 'dark' ? 'bg-zinc-950' : 'bg-slate-50'}`}>
      <div className={`flex flex-col flex-1 transition-all duration-300`}>
        {/* Header */}
        <header className={`flex items-center gap-4 px-6 py-4 border-b shadow-sm z-10 ${
          theme === 'dark' ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-slate-200'
        }`}>
          <button
            onClick={() => navigate(-1)}
            className={`p-2 rounded-lg transition-colors ${
              theme === 'dark' ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-slate-100 text-slate-600'
            }`}
          >
            <ChevronLeft size={18} />
          </button>
          <h1 className={`font-semibold text-sm ${theme === 'dark' ? 'text-zinc-100' : 'text-slate-800'}`}>
            Settings
          </h1>
          {saved && (
            <span className="flex items-center gap-1 text-xs text-green-500 ml-auto">
              <Check size={14} /> Saved
            </span>
          )}
        </header>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar Tabs */}
          <nav className={`w-52 border-r p-3 space-y-1 ${
            theme === 'dark' ? 'border-zinc-800 bg-zinc-900' : 'border-slate-200 bg-white'
          }`}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeTab === tab.id
                    ? theme === 'dark' ? 'bg-zinc-800 text-white' : 'bg-slate-100 text-slate-900'
                    : theme === 'dark' ? 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'profile' && (
              <div className="max-w-xl space-y-8">
                <div>
                  <h2 className={`text-lg font-semibold mb-4 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Profile</h2>
                  <div className={`p-5 rounded-xl space-y-4 ${theme === 'dark' ? 'bg-zinc-900 border border-zinc-800' : 'bg-white border border-slate-200'}`}>
                    <div>
                      <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>Name</label>
                      <input
                        type="text" value={name} onChange={e => setName(e.target.value)}
                        className={`w-full px-3 py-2 rounded-lg border text-sm outline-none transition ${
                          theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white focus:border-blue-500' : 'bg-white border-slate-200 text-slate-900 focus:border-blue-400'
                        }`}
                      />
                    </div>
                    <div>
                      <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>Email</label>
                      <input
                        type="email" value={email} onChange={e => setEmail(e.target.value)}
                        className={`w-full px-3 py-2 rounded-lg border text-sm outline-none transition ${
                          theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white focus:border-blue-500' : 'bg-white border-slate-200 text-slate-900 focus:border-blue-400'
                        }`}
                      />
                    </div>
                    <div className={`text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                      Role: <span className="font-medium">{user?.role}</span>
                    </div>
                    <button
                      onClick={handleSaveProfile}
                      className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition shadow-sm"
                    >
                      <Save size={14} /> Save Profile
                    </button>
                  </div>
                </div>

                <div>
                  <h2 className={`text-lg font-semibold mb-4 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Change Password</h2>
                  <div className={`p-5 rounded-xl space-y-4 ${theme === 'dark' ? 'bg-zinc-900 border border-zinc-800' : 'bg-white border border-slate-200'}`}>
                    <div>
                      <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>Current Password</label>
                      <div className="relative">
                        <input
                          type={showPassword ? 'text' : 'password'} value={currentPassword}
                          onChange={e => setCurrentPassword(e.target.value)}
                          className={`w-full px-3 py-2 pr-10 rounded-lg border text-sm outline-none transition ${
                            theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white focus:border-blue-500' : 'bg-white border-slate-200 text-slate-900 focus:border-blue-400'
                          }`}
                        />
                        <button onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-2.5 text-zinc-400">
                          {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>New Password</label>
                      <input
                        type={showPassword ? 'text' : 'password'} value={newPassword}
                        onChange={e => setNewPassword(e.target.value)}
                        className={`w-full px-3 py-2 rounded-lg border text-sm outline-none transition ${
                          theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white focus:border-blue-500' : 'bg-white border-slate-200 text-slate-900 focus:border-blue-400'
                        }`}
                      />
                    </div>
                    {passwordError && <p className="text-xs text-red-500">{passwordError}</p>}
                    {passwordSuccess && <p className="text-xs text-green-500">{passwordSuccess}</p>}
                    <button
                      onClick={handleChangePassword}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition shadow-sm"
                    >
                      Change Password
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'appearance' && (
              <div className="max-w-xl space-y-6">
                <h2 className={`text-lg font-semibold mb-4 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Appearance</h2>
                <div className={`p-5 rounded-xl space-y-5 ${theme === 'dark' ? 'bg-zinc-900 border border-zinc-800' : 'bg-white border border-slate-200'}`}>
                  <div>
                    <label className={`block text-xs font-medium mb-2 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>Theme</label>
                    <div className="flex gap-3">
                      {[
                        { id: 'light', label: 'Light', icon: <Sun size={16} /> },
                        { id: 'dark', label: 'Dark', icon: <Moon size={16} /> },
                      ].map(t => (
                        <button
                          key={t.id}
                          onClick={() => setTheme(t.id as 'light' | 'dark')}
                          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-xs font-medium transition ${
                            currentTheme === t.id
                              ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
                              : theme === 'dark' ? 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                          }`}
                        >
                          {t.icon} {t.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-sm font-medium ${theme === 'dark' ? 'text-zinc-200' : 'text-slate-700'}`}>Compact Mode</p>
                      <p className={`text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>Reduce spacing in chat and dashboards</p>
                    </div>
                    <button
                      onClick={() => setCompactMode(!compactMode)}
                      className={`w-10 h-6 rounded-full transition-colors ${compactMode ? 'bg-blue-600' : theme === 'dark' ? 'bg-zinc-700' : 'bg-slate-200'}`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-white transform transition-transform ${compactMode ? 'translate-x-5' : 'translate-x-1'} mt-1`} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-sm font-medium ${theme === 'dark' ? 'text-zinc-200' : 'text-slate-700'}`}>Animations</p>
                      <p className={`text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>Enable transitions and micro-interactions</p>
                    </div>
                    <button
                      onClick={() => setAnimations(!animations)}
                      className={`w-10 h-6 rounded-full transition-colors ${animations ? 'bg-blue-600' : theme === 'dark' ? 'bg-zinc-700' : 'bg-slate-200'}`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-white transform transition-transform ${animations ? 'translate-x-5' : 'translate-x-1'} mt-1`} />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'ai-preferences' && (
              <div className="max-w-xl space-y-6">
                <h2 className={`text-lg font-semibold mb-4 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>AI Preferences</h2>
                <div className={`p-5 rounded-xl space-y-5 ${theme === 'dark' ? 'bg-zinc-900 border border-zinc-800' : 'bg-white border border-slate-200'}`}>
                  <div>
                    <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>Custom Instructions</label>
                    <p className={`text-xs mb-2 ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>Tell the AI how to respond to you.</p>
                    <textarea
                      value={customInstructions}
                      onChange={e => setCustomInstructions(e.target.value)}
                      placeholder="e.g. Always include SQL explanations, prefer bar charts..."
                      rows={3}
                      className={`w-full px-3 py-2 rounded-lg border text-sm outline-none resize-none transition ${
                        theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-600 focus:border-blue-500' : 'bg-white border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-blue-400'
                      }`}
                    />
                  </div>

                  <div>
                    <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>Preferred Chart Type</label>
                    <select
                      value={preferredChart}
                      onChange={e => setPreferredChart(e.target.value)}
                      className={`w-full px-3 py-2 rounded-lg border text-sm outline-none transition ${
                        theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white focus:border-blue-500' : 'bg-white border-slate-200 text-slate-900 focus:border-blue-400'
                      }`}
                    >
                      <option value="auto">Auto (AI decides)</option>
                      <option value="bar">Bar Chart</option>
                      <option value="line">Line Chart</option>
                      <option value="pie">Pie Chart</option>
                      <option value="area">Area Chart</option>
                      <option value="table">Table</option>
                    </select>
                  </div>

                  <div>
                    <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>Response Length</label>
                    <select
                      value={responseLength}
                      onChange={e => setResponseLength(e.target.value)}
                      className={`w-full px-3 py-2 rounded-lg border text-sm outline-none transition ${
                        theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white focus:border-blue-500' : 'bg-white border-slate-200 text-slate-900 focus:border-blue-400'
                      }`}
                    >
                      <option value="concise">Concise</option>
                      <option value="balanced">Balanced</option>
                      <option value="detailed">Detailed</option>
                    </select>
                  </div>

                  <div>
                    <label className={`block text-xs font-medium mb-2 ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>Saved Prompts</label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text" value={newPrompt}
                        onChange={e => setNewPrompt(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleAddPrompt()}
                        placeholder="Add a saved prompt..."
                        className={`flex-1 px-3 py-2 rounded-lg border text-sm outline-none transition ${
                          theme === 'dark' ? 'bg-zinc-800 border-zinc-700 text-white placeholder:text-zinc-600 focus:border-blue-500' : 'bg-white border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-blue-400'
                        }`}
                      />
                      <button
                        onClick={handleAddPrompt}
                        className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition"
                      >
                        Add
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {savedPrompts.map(p => (
                        <span key={p} className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs ${
                          theme === 'dark' ? 'bg-zinc-800 text-zinc-300' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {p}
                          <button onClick={() => handleRemovePrompt(p)} className="text-zinc-400 hover:text-red-400">
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <button
                  onClick={handleSavePreferences}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition shadow-sm"
                >
                  <Save size={14} /> Save Preferences
                </button>
              </div>
            )}

            {activeTab === 'notifications' && (
              <div className="max-w-xl space-y-6">
                <h2 className={`text-lg font-semibold mb-4 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Notifications</h2>
                <div className={`p-5 rounded-xl space-y-5 ${theme === 'dark' ? 'bg-zinc-900 border border-zinc-800' : 'bg-white border border-slate-200'}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-sm font-medium ${theme === 'dark' ? 'text-zinc-200' : 'text-slate-700'}`}>Email Notifications</p>
                      <p className={`text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>Receive updates via email</p>
                    </div>
                    <button
                      onClick={() => setEmailNotifications(!emailNotifications)}
                      className={`w-10 h-6 rounded-full transition-colors ${emailNotifications ? 'bg-blue-600' : theme === 'dark' ? 'bg-zinc-700' : 'bg-slate-200'}`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-white transform transition-transform ${emailNotifications ? 'translate-x-5' : 'translate-x-1'} mt-1`} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-sm font-medium ${theme === 'dark' ? 'text-zinc-200' : 'text-slate-700'}`}>Push Notifications</p>
                      <p className={`text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>Browser push notifications for alerts</p>
                    </div>
                    <button
                      onClick={() => setPushNotifications(!pushNotifications)}
                      className={`w-10 h-6 rounded-full transition-colors ${pushNotifications ? 'bg-blue-600' : theme === 'dark' ? 'bg-zinc-700' : 'bg-slate-200'}`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-white transform transition-transform ${pushNotifications ? 'translate-x-5' : 'translate-x-1'} mt-1`} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-sm font-medium ${theme === 'dark' ? 'text-zinc-200' : 'text-slate-700'}`}>Weekly Digest</p>
                      <p className={`text-xs ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>Weekly summary of your queries and insights</p>
                    </div>
                    <button
                      onClick={() => setWeeklyDigest(!weeklyDigest)}
                      className={`w-10 h-6 rounded-full transition-colors ${weeklyDigest ? 'bg-blue-600' : theme === 'dark' ? 'bg-zinc-700' : 'bg-slate-200'}`}
                    >
                      <div className={`w-4 h-4 rounded-full bg-white transform transition-transform ${weeklyDigest ? 'translate-x-5' : 'translate-x-1'} mt-1`} />
                    </button>
                  </div>
                </div>
                <button
                  onClick={handleSavePreferences}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition shadow-sm"
                >
                  <Save size={14} /> Save Preferences
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
