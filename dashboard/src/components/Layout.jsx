import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import './Layout.css'

function Layout() {
  return (
    <div className="app-container">
      <Sidebar />
      <Header />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}

export default Layout
