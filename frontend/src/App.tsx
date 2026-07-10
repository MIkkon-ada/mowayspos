import { BrowserRouter } from 'react-router-dom'
import { ProjectProvider } from './context/ProjectContext'
import { AppRoutes } from './app/routes'
import { Toaster } from './components/Toaster'

export default function App() {
  return (
    <BrowserRouter>
      <ProjectProvider>
        <AppRoutes />
        <Toaster />
      </ProjectProvider>
    </BrowserRouter>
  )
}
