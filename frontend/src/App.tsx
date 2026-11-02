import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardLayout } from './layouts/DashboardLayout';
import { MarketOverviewPage } from './pages/MarketOverviewPage';
import { StockResearchPage } from './pages/StockResearchPage';
import { NewsExplorerPage } from './pages/NewsExplorerPage';
import { MLLabPage } from './pages/MLLabPage';
import { BacktestingLabPage } from './pages/BacktestingLabPage';
import { SystemHealthPage } from './pages/SystemHealthPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,   // default off — price queries override to true
      retry: 1,
      staleTime: 5000,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardLayout />}>
            <Route index element={<MarketOverviewPage />} />
            <Route path="research" element={<StockResearchPage />} />
            <Route path="news" element={<NewsExplorerPage />} />
            <Route path="ml-lab" element={<MLLabPage />} />
            <Route path="backtesting" element={<BacktestingLabPage />} />
            <Route path="health" element={<SystemHealthPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
