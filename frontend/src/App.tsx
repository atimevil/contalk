import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import ToastContainer from './components/Toast';

import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import AnalyzingPage from './pages/AnalyzingPage';
import ResultPage from './pages/ResultPage';
import SpecialClausesPage from './pages/SpecialClausesPage';
import ChecklistPage from './pages/ChecklistPage';
import PaymentPage from './pages/PaymentPage';
import LoginPage from './pages/LoginPage';
import OAuthCallbackPage from './pages/OAuthCallbackPage';
import MyPage from './pages/MyPage';
import ErrorPage from './pages/ErrorPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 1 * 60 * 1000, // 1분
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <ToastProvider>
            <ToastContainer />
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/analyzing/:jobId" element={<AnalyzingPage />} />
              <Route path="/report/:reportId" element={<ResultPage />} />
              <Route path="/report/:reportId/clauses" element={<SpecialClausesPage />} />
              <Route path="/checklist" element={<ChecklistPage />} />
              <Route path="/payment" element={<PaymentPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/oauth/:provider/callback" element={<OAuthCallbackPage />} />
              <Route path="/mypage" element={<MyPage />} />
              <Route path="/error" element={<ErrorPage />} />
              <Route path="*" element={<ErrorPage />} />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
