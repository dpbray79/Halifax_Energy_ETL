import { NavLink } from 'react-router-dom'
import { LayoutDashboard, LineChart, Database } from 'lucide-react'
import './Sidebar.css'

function Sidebar() {
  const navItems = [
    {
      to: '/dashboard',
      icon: <LayoutDashboard size={20} />,
      label: 'Dashboard'
    },
    {
      to: '/models',
      icon: <LineChart size={20} />,
      label: 'Models'
    },
    {
      to: '/data',
      icon: <Database size={20} />,
      label: 'Data'
    }
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>Halifax Energy</h2>
        <p className="text-xs text-muted">Demand Forecasting</p>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'active' : ''}`
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="text-xs text-muted">
          <p>NSCC DBAS 3090</p>
          <p>Dylan Bray • March 2026</p>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
