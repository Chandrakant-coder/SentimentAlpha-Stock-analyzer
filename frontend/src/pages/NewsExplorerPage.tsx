import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  Filter,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Layers,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { useNavigate } from 'react-router-dom';

export const NewsExplorerPage: React.FC = () => {
  const navigate = useNavigate();
  const [page, setPage] = useState<number>(1);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedStock, setSelectedStock] = useState<string>('');
  const [selectedSentiment, setSelectedSentiment] = useState<string>('');
  const [selectedSource, setSelectedSource] = useState<string>('');

  const { data: stocks } = useQuery({
    queryKey: ['stocks'],
    queryFn: () => apiClient.getStocks(),
  });

  const { data: newsData, isLoading } = useQuery({
    queryKey: ['news', page, selectedStock, selectedSentiment, selectedSource, searchTerm],
    queryFn: () =>
      apiClient.getNews({
        page,
        page_size: 15,
        symbol: selectedStock || undefined,
        sentiment: selectedSentiment || undefined,
        source: selectedSource || undefined,
        search: searchTerm || undefined,
      }),
  });

  const handleResetFilters = () => {
    setSearchTerm('');
    setSelectedStock('');
    setSelectedSentiment('');
    setSelectedSource('');
    setPage(1);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            FINANCIAL NEWS & FINBERT INTELLIGENCE EXPLORER
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Browse real financial RSS articles, entity mapping, and raw NLP sentiment probability distributions.
          </p>
        </div>

        <div className="text-xs font-mono text-slate-400">
          Showing <span className="text-white font-bold">{newsData?.items?.length || 0}</span> of{' '}
          <span className="text-cyan-400 font-bold">{newsData?.total || 0}</span> articles
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-4 flex flex-wrap items-center gap-3 font-mono text-xs">
        {/* Search Input */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
            }}
            placeholder="Search headlines or descriptions..."
            className="w-full bg-slate-900/80 border border-slate-700/80 rounded-lg pl-9 pr-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Stock Filter */}
        <select
          value={selectedStock}
          onChange={(e) => {
            setSelectedStock(e.target.value);
            setPage(1);
          }}
          className="bg-slate-900/80 border border-slate-700/80 text-white rounded-lg px-3 py-2 focus:outline-none focus:border-cyan-500"
        >
          <option value="">All Stocks</option>
          {stocks?.map((s) => (
            <option key={s.symbol} value={s.symbol}>
              {s.symbol}
            </option>
          ))}
        </select>

        {/* Sentiment Filter */}
        <select
          value={selectedSentiment}
          onChange={(e) => {
            setSelectedSentiment(e.target.value);
            setPage(1);
          }}
          className="bg-slate-900/80 border border-slate-700/80 text-white rounded-lg px-3 py-2 focus:outline-none focus:border-cyan-500"
        >
          <option value="">All Sentiments</option>
          <option value="positive">Positive (Bullish)</option>
          <option value="negative">Negative (Bearish)</option>
          <option value="neutral">Neutral</option>
        </select>

        {/* Source Filter */}
        <select
          value={selectedSource}
          onChange={(e) => {
            setSelectedSource(e.target.value);
            setPage(1);
          }}
          className="bg-slate-900/80 border border-slate-700/80 text-white rounded-lg px-3 py-2 focus:outline-none focus:border-cyan-500"
        >
          <option value="">All Sources</option>
          <option value="Economic Times">Economic Times</option>
          <option value="Moneycontrol">Moneycontrol</option>
          <option value="Livemint">Livemint</option>
          <option value="Yahoo">Yahoo Finance</option>
        </select>

        {(searchTerm || selectedStock || selectedSentiment || selectedSource) && (
          <button
            onClick={handleResetFilters}
            className="px-3 py-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white transition-colors"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Article List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="text-center py-12 text-slate-500 font-mono text-xs">
            Loading articles...
          </div>
        ) : newsData?.items && newsData.items.length > 0 ? (
          newsData.items.map((art) => {
            const sent = art.sentiment;
            const isPos = sent?.sentiment_label === 'positive';
            const isNeg = sent?.sentiment_label === 'negative';

            return (
              <div
                key={art.id}
                className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5 hover:border-slate-700/80 transition-all flex flex-col md:flex-row md:items-center justify-between gap-6"
              >
                <div className="space-y-2 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      {art.source}
                    </span>
                    <span className="text-slate-600">•</span>
                    <span className="text-[10px] font-mono text-slate-500">
                      {art.published_at.replace('T', ' ').slice(0, 16)} UTC
                    </span>

                    {/* Mapped Stocks Chips */}
                    {art.mapped_stocks && art.mapped_stocks.length > 0 && (
                      <div className="flex items-center gap-1.5 ml-2">
                        {art.mapped_stocks.map((sym) => (
                          <span
                            key={sym}
                            onClick={() => navigate(`/research?symbol=${sym}`)}
                            className="text-[10px] font-mono font-bold bg-cyan-950/60 text-cyan-300 border border-cyan-800/60 px-2 py-0.5 rounded cursor-pointer hover:bg-cyan-900/60 transition-colors"
                          >
                            ${sym}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <a
                    href={art.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-semibold text-white hover:text-cyan-400 flex items-center gap-1.5 transition-colors leading-snug"
                  >
                    <span>{art.title}</span>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                  </a>

                  {art.description && (
                    <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                      {art.description}
                    </p>
                  )}
                </div>

                {/* Sentiment Inference Breakdown */}
                {sent ? (
                  <div className="shrink-0 w-full md:w-64 flex flex-col gap-2 font-mono bg-slate-900/70 p-3 rounded-lg border border-slate-800/60">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-slate-400 uppercase">FinBERT Inference</span>
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded ${
                          isPos
                            ? 'text-emerald-400 bg-emerald-950/80 border border-emerald-800/80'
                            : isNeg
                            ? 'text-rose-400 bg-rose-950/80 border border-rose-800/80'
                            : 'text-slate-300 bg-slate-800/80 border border-slate-700'
                        }`}
                      >
                        {sent.sentiment_label.toUpperCase()} ({sent.sentiment_score > 0 ? '+' : ''}
                        {sent.sentiment_score.toFixed(2)})
                      </span>
                    </div>

                    {/* Probability Distribution Bar */}
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden flex">
                      <div
                        className="bg-emerald-500 h-full"
                        style={{ width: `${(sent.positive_probability * 100).toFixed(1)}%` }}
                        title={`Positive: ${(sent.positive_probability * 100).toFixed(1)}%`}
                      />
                      <div
                        className="bg-slate-500 h-full"
                        style={{ width: `${(sent.neutral_probability * 100).toFixed(1)}%` }}
                        title={`Neutral: ${(sent.neutral_probability * 100).toFixed(1)}%`}
                      />
                      <div
                        className="bg-rose-500 h-full"
                        style={{ width: `${(sent.negative_probability * 100).toFixed(1)}%` }}
                        title={`Negative: ${(sent.negative_probability * 100).toFixed(1)}%`}
                      />
                    </div>

                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span className="text-emerald-400">Pos: {(sent.positive_probability * 100).toFixed(0)}%</span>
                      <span className="text-slate-400">Neu: {(sent.neutral_probability * 100).toFixed(0)}%</span>
                      <span className="text-rose-400">Neg: {(sent.negative_probability * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ) : (
                  <div className="shrink-0 flex items-center justify-center p-4 bg-slate-900/40 rounded-lg border border-slate-800 text-[11px] font-mono text-amber-400">
                    Inference Pending
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <div className="text-center py-16 text-slate-500 font-mono text-xs">
            No articles match the specified filters.
          </div>
        )}
      </div>

      {/* Pagination Bar */}
      {newsData && newsData.pages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-800/80 pt-4 font-mono text-xs">
          <div className="text-slate-400">
            Page {newsData.page} of {newsData.pages}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Previous</span>
            </button>

            <button
              onClick={() => setPage((p) => Math.min(newsData.pages, p + 1))}
              disabled={page >= newsData.pages}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white disabled:opacity-40 transition-colors"
            >
              <span>Next</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
