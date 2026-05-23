import React from 'react'
import ReactECharts from 'echarts-for-react'
import { CopilotWidget } from '../components/Chat/CopilotWidget'
import { useThemeStore } from '../store/theme'
import { useAuthStore } from '../store/auth'
import { BarChart2, TrendingUp, Users, ShoppingBag, AlertCircle, LogOut, Settings, Layout, Sun, Moon } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const DummyClientWebsite: React.FC = () => {
  const { theme, toggleTheme } = useThemeStore()
  const { user, clearAuth } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    clearAuth()
    navigate('/login')
  }

  // ECharts Line Chart Configuration (Revenue Trend)
  const getLineChartOption = () => {
    const isDark = theme === 'dark'
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      grid: {
        top: 40,
        bottom: 40,
        left: 50,
        right: 20
      },
      xAxis: {
        type: 'category',
        data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        axisLine: {
          lineStyle: { color: isDark ? '#2e2e33' : '#e2e8f0' }
        },
        axisLabel: {
          color: isDark ? '#8e9297' : '#64748b'
        }
      },
      yAxis: {
        type: 'value',
        splitLine: {
          lineStyle: { color: isDark ? '#1e1f22' : '#f1f5f9' }
        },
        axisLabel: {
          color: isDark ? '#8e9297' : '#64748b'
        }
      },
      series: [
        {
          name: 'Revenue',
          data: [12000, 19000, 15000, 22000, 26000, 32000, 28000],
          type: 'line',
          smooth: true,
          lineStyle: {
            width: 3.5,
            color: '#3b82f6'
          },
          itemStyle: {
            color: '#3b82f6'
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
                { offset: 1, color: 'rgba(59, 130, 246, 0)' }
              ]
            }
          }
        }
      ]
    }
  }

  // Echarts Category Chart Option (Brand Breakdown)
  const getBarChartOption = () => {
    const isDark = theme === 'dark'
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: {
        top: 40,
        bottom: 40,
        left: 50,
        right: 20
      },
      xAxis: {
        type: 'category',
        data: ['Klairs', 'By Wishtrend', 'I\'m From', 'COSRX', 'Beauty of Joseon'],
        axisLine: {
          lineStyle: { color: isDark ? '#2e2e33' : '#e2e8f0' }
        },
        axisLabel: {
          color: isDark ? '#8e9297' : '#64748b',
          fontSize: 10
        }
      },
      yAxis: {
        type: 'value',
        splitLine: {
          lineStyle: { color: isDark ? '#1e1f22' : '#f1f5f9' }
        },
        axisLabel: {
          color: isDark ? '#8e9297' : '#64748b'
        }
      },
      series: [
        {
          name: 'Units Sold',
          data: [4200, 2800, 3100, 5400, 4800],
          type: 'bar',
          barWidth: '40%',
          itemStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: '#8b5cf6' },
                { offset: 1, color: '#6366f1' }
              ]
            },
            borderRadius: [4, 4, 0, 0]
          }
        }
      ]
    }
  }

  // Mock table data
  const recentOrders = [
    { id: 'ORD-89312', customer: 'Ananya Sharma', product: 'Klairs Supple Preparation Toner', amount: '₹1,430', status: 'Delivered', date: 'May 23, 2026' },
    { id: 'ORD-89311', customer: 'Rahul Verma', product: 'COSRX Snail Mucin Essence', amount: '₹1,970', status: 'Processing', date: 'May 23, 2026' },
    { id: 'ORD-89310', customer: 'Priya Patel', product: 'I\'m From Honey Mask', amount: '₹2,650', status: 'Delivered', date: 'May 22, 2026' },
    { id: 'ORD-89309', customer: 'Amit Singh', product: 'By Wishtrend Vitamin Drop', amount: '₹1,850', status: 'Shipped', date: 'May 22, 2026' },
    { id: 'ORD-89308', customer: 'Sneha Reddy', product: 'Klairs Midnight Blue Calming Cream', amount: '₹2,100', status: 'Delivered', date: 'May 21, 2026' },
  ]

  return (
    <div className={`min-h-screen font-sans transition-colors duration-350 ${
      theme === 'dark' ? 'bg-[#0B0C0E] text-[#E3E4E6]' : 'bg-[#fafafa] text-[#1f2937]'
    }`}>
      {/* Navbar */}
      <nav className={`sticky top-0 z-30 flex items-center justify-between px-6 py-4 border-b ${
        theme === 'dark' ? 'bg-[#121214] border-[#2A2B2F]' : 'bg-white border-slate-200'
      } shadow-xs`}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg">
            <span className="text-white font-extrabold text-sm tracking-wider">L</span>
          </div>
          <div>
            <h1 className="font-bold text-sm leading-tight text-slate-800 dark:text-zinc-100">
              Limese Retailer Portal
            </h1>
            <p className="text-[10px] text-zinc-400 font-medium">Partner Dashboard</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={toggleTheme}
            className={`p-2 rounded-lg border hover:bg-slate-100 dark:hover:bg-zinc-800 transition-all ${
              theme === 'dark' ? 'border-zinc-800 text-zinc-300' : 'border-slate-200 text-slate-600'
            }`}
            title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
          >
            {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          </button>
          


          <div className={`h-6 w-px ${theme === 'dark' ? 'bg-zinc-850' : 'bg-slate-200'}`} />

          <div className="flex items-center gap-2.5">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white bg-gradient-to-tr from-blue-500 to-indigo-500`}>
              {user?.name?.charAt(0) || 'U'}
            </div>
            <div className="hidden md:block">
              <div className="text-xs font-bold leading-tight">{user?.name || 'Partner Account'}</div>
              <div className="text-[9px] text-zinc-400 font-medium capitalize">{user?.role || 'Guest'}</div>
            </div>
            <button
              onClick={handleLogout}
              className={`p-1.5 hover:text-red-500 rounded-lg hover:bg-red-50/10 transition`}
              title="Logout"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        
        {/* Banner Section */}
        <div className={`p-6 mb-8 rounded-2xl bg-gradient-to-r ${
          theme === 'dark' 
            ? 'from-zinc-900 via-zinc-900/60 to-transparent border border-zinc-850' 
            : 'from-blue-50/50 via-indigo-50/20 to-transparent border border-slate-150'
        } relative overflow-hidden`}>
          <div className="relative z-10 max-w-xl">
            <h2 className="text-xl font-bold mb-1 bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent dark:from-blue-400 dark:to-indigo-400">
              Welcome to your Partner Console
            </h2>
            <p className={`text-xs leading-relaxed ${theme === 'dark' ? 'text-zinc-400' : 'text-slate-500'}`}>
              Check your analytics, monitor sales pipeline, track product catalog levels, and get real-time answers. Try clicking the floating widget in the bottom right corner for immediate natural language insights.
            </p>
          </div>
          <div className="absolute right-0 top-0 bottom-0 opacity-10 pointer-events-none flex items-center justify-end pr-10">
            <BarChart2 size={180} className="text-indigo-500 animate-pulse" />
          </div>
        </div>

        {/* Dashboard Grid - 4 KPI metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
          {[
            { title: 'Weekly Revenue', value: '₹1,98,450.00', sub: '+12.4% vs last week', icon: <TrendingUp size={16} className="text-green-500" />, bg: 'from-green-500/10 to-emerald-500/10 border-green-500/20' },
            { title: 'Units Shipped', value: '14,234 units', sub: '+4.8% vs last week', icon: <ShoppingBag size={16} className="text-blue-500" />, bg: 'from-blue-500/10 to-indigo-500/10 border-blue-500/20' },
            { title: 'Retail Conversion', value: '3.24%', sub: '+0.12% vs last month', icon: <Users size={16} className="text-purple-500" />, bg: 'from-purple-500/10 to-pink-500/10 border-purple-500/20' },
            { title: 'Fulfillment Alerts', value: '42 issues', sub: '-15% unresolved', icon: <AlertCircle size={16} className="text-amber-500" />, bg: 'from-amber-500/10 to-orange-500/10 border-amber-500/20' },
          ].map((kpi, idx) => (
            <div
              key={idx}
              className={`p-5 rounded-2xl border transition-all duration-300 hover:-translate-y-1 shadow-sm ${
                theme === 'dark' 
                  ? 'bg-[#121214] border-[#2A2B2F] hover:border-zinc-700' 
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className={`text-[11px] font-bold tracking-wider uppercase ${theme === 'dark' ? 'text-zinc-500' : 'text-slate-400'}`}>
                  {kpi.title}
                </span>
                <span className={`p-1.5 rounded-lg flex items-center justify-center ${theme === 'dark' ? 'bg-zinc-800' : 'bg-slate-50'}`}>
                  {kpi.icon}
                </span>
              </div>
              <div className="text-xl font-bold mb-1 tracking-tight">{kpi.value}</div>
              <div className="text-[10px] text-zinc-400 font-medium flex items-center gap-1">
                {kpi.sub}
              </div>
            </div>
          ))}
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Revenue Trend Line Chart */}
          <div className={`col-span-2 p-5 rounded-2xl border ${
            theme === 'dark' ? 'bg-[#121214] border-[#2A2B2F]' : 'bg-white border-slate-200'
          } shadow-sm`}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-xs">Revenue Development</h3>
                <p className="text-[10px] text-zinc-400">Weekly sales tracking for Limese brands</p>
              </div>
              <div className="flex items-center gap-1 text-[10px] font-semibold text-blue-500 bg-blue-500/10 rounded-lg px-2.5 py-1">
                Live Data
              </div>
            </div>
            <div className="h-64">
              <ReactECharts option={getLineChartOption()} style={{ height: '100%', width: '150%' }} opts={{ renderer: 'canvas' }} />
            </div>
          </div>

          {/* Brand Breakdown Bar Chart */}
          <div className={`p-5 rounded-2xl border ${
            theme === 'dark' ? 'bg-[#121214] border-[#2A2B2F]' : 'bg-white border-slate-200'
          } shadow-sm`}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-xs">Top Selling Brands</h3>
                <p className="text-[10px] text-zinc-400">Units processed per brand</p>
              </div>
            </div>
            <div className="h-64">
              <ReactECharts option={getBarChartOption()} style={{ height: '100%' }} />
            </div>
          </div>
        </div>

        {/* Recent Orders Table */}
        <div className={`p-5 rounded-2xl border ${
          theme === 'dark' ? 'bg-[#121214] border-[#2A2B2F]' : 'bg-white border-slate-200'
        } shadow-sm`}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-xs">Recent Wholesale Shipments</h3>
              <p className="text-[10px] text-zinc-400">Real-time orders processed today</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className={`border-b ${theme === 'dark' ? 'border-zinc-800' : 'border-slate-100'} text-zinc-400`}>
                  <th className="pb-3 font-semibold">Order ID</th>
                  <th className="pb-3 font-semibold">Customer</th>
                  <th className="pb-3 font-semibold">Product Purchased</th>
                  <th className="pb-3 font-semibold">Total Amount</th>
                  <th className="pb-3 font-semibold">Status</th>
                  <th className="pb-3 font-semibold">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                {recentOrders.map((ord, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-zinc-900/50 transition">
                    <td className="py-3 font-mono font-bold text-[11px] text-indigo-500">{ord.id}</td>
                    <td className="py-3 font-semibold">{ord.customer}</td>
                    <td className="py-3 text-zinc-500 dark:text-zinc-400">{ord.product}</td>
                    <td className="py-3 font-bold">{ord.amount}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        ord.status === 'Delivered' 
                          ? 'bg-green-500/10 text-green-500' 
                          : ord.status === 'Processing'
                          ? 'bg-blue-500/10 text-blue-500'
                          : 'bg-amber-500/10 text-amber-500'
                      }`}>
                        {ord.status}
                      </span>
                    </td>
                    <td className="py-3 text-zinc-400">{ord.date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Floating right-side Copilot Widget */}
      <CopilotWidget />
    </div>
  )
}

export default DummyClientWebsite
