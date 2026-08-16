import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Items from './pages/Items'
import ItemDetail from './pages/ItemDetail'
import Settings from './pages/Settings'
import System from './pages/System'
import Help from './pages/Help'
import { ToastProvider } from './components/ui/Toast'
import { PreferencesProvider } from './context/PreferencesContext'

function App() {
  return (
    <PreferencesProvider>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="items" element={<Items />} />
            <Route path="items/:id" element={<ItemDetail />} />
            <Route path="settings" element={<Settings />} />
            <Route path="system" element={<System />} />
            <Route path="help" element={<Help />} />
          </Route>
        </Routes>
      </ToastProvider>
    </PreferencesProvider>
  )
}

export default App
