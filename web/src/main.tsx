import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { I18nProvider } from '@lingui/react'
import './index.css'
import App from './App'
import { i18n, activateLocale, DEFAULT_LOCALE } from './i18n/init'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,
      gcTime: 5 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: true,
    },
  },
})

// Activate the default locale before first render so strings resolve from a
// loaded catalog rather than falling back to source IDs. LocaleContext will
// switch to the user's preferred locale after auth and settings load.
activateLocale(DEFAULT_LOCALE)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </I18nProvider>
  </StrictMode>,
)
