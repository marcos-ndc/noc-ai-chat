import { createRoot } from 'react-dom/client'
import './styles/globals.css'
import App from './App.tsx'

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

// StrictMode desabilitado: em dev monta componentes 2x para detectar side-effects,
// mas isso causa dupla conexão WebSocket e é confuso nos logs.
// Reabilitar em produção é seguro pois não há double-mount em prod.
createRoot(root).render(
  <App />
)
