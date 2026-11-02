import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Sliders,
  TrendingUp,
  Percent,
  Play,
  RotateCcw,
  ShieldCheck,
  AlertCircle,
  FileSpreadsheet,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { apiClient } from '../api/client';
import { BacktestRun } from '../types';

export const BacktestingLabPage: React.FC = () => {
  const [symbol, setSymbol] = useState<string>('RELIANCE');
  const [strategyType, setStrategyType] = useState<string>('sentiment_momentum');
  const [initialCapital, setInitialCapital] = useState<number>(100000);
  const [entryThreshold, setEntryThreshold] = useState<number>(0.15);
  const [exitThreshold, setExitThreshold] = useState<number>(-0.05);
  const [transactionCost, setTransactionCost] = useState<number>(0.001); // 10 bps
  const [slippage, setSlippage] = useState<number>(0.0005); // 5 bps

  const [activeBacktest, setActiveBacktest] = useState<BacktestRun | null>(null);

  const { data: stocks } = useQuery({
    queryKey: ['stocks'],
    queryFn: () => apiClient.getStocks(),
  });

  const { data: backtestList, refetch: refetchList } = useQuery({
    queryKey: ['backtests'],
    queryFn: () => apiClient.getBacktests(),
  });

  // Pick first backtest when list loads if none active
  React.useEffect(() => {
    if (backtestList && backtestList.length > 0 && !activeBacktest) {
      setActiveBacktest(backtestList[0]);
    }
  }, [backtestList, activeBacktest]);

  const backtestMutation = useMutation({
    mutationFn: apiClient.runBacktest,
    onSuccess: (data) => {
      setActiveBacktest(data);
      refetchList();
    },
  });

  const handleRunBacktest = () => {
    backtestMutation.mutate({
      symbol,
      strategy_type: strategyType,
      initial_capital: initialCapital,
      entry_sentiment_threshold: entryThreshold,
      exit_sentiment_threshold: exitThreshold,
      transaction_cost_pct: transactionCost,
      slippage_pct: slippage,
    });
  };

  const trades = activeBacktest?.trades || [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
            <Sliders className="w-5 h-5 text-cyan-400" />
            QUANTITATIVE BACKTESTING ENGINE
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Realistic long-only strategy simulation with session-next execution, slippage, and fee accounting.
          </p>
        </div>
      </div>

      {/* Strategy Configuration & Key Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Column: Form Controls */}
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-800">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              Strategy Parameters
            </span>
          </div>

          {/* Stock Symbol */}
          <div className="space-y-1">
            <label className="text-xs font-mono text-slate-400">Target Asset</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg p-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-500"
            >
              {stocks?.map((s) => (
                <option key={s.symbol} value={s.symbol}>
                  {s.symbol} ({s.company_name})
                </option>
              ))}
            </select>
          </div>

          {/* Strategy Model */}
          <div className="space-y-1">
            <label className="text-xs font-mono text-slate-400">Trading Model</label>
            <select
              value={strategyType}
              onChange={(e) => setStrategyType(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg p-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="sentiment_momentum">Sentiment Momentum + Trend Filter</option>
              <option value="simple_sentiment">Pure Sentiment Threshold</option>
            </select>
          </div>

          {/* Capital */}
          <div className="space-y-1">
            <label className="text-xs font-mono text-slate-400">Initial Capital (INR)</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg p-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Entry Sentiment Threshold */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-400">Entry Sentiment</span>
              <span className="text-emerald-400 font-bold">+{entryThreshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="0.5"
              step="0.05"
              value={entryThreshold}
              onChange={(e) => setEntryThreshold(Number(e.target.value))}
              className="w-full accent-cyan-500 cursor-pointer"
            />
          </div>

          {/* Exit Sentiment Threshold */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-400">Exit Sentiment</span>
              <span className="text-rose-400 font-bold">{exitThreshold.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="-0.5"
              max="0.1"
              step="0.05"
              value={exitThreshold}
              onChange={(e) => setExitThreshold(Number(e.target.value))}
              className="w-full accent-cyan-500 cursor-pointer"
            />
          </div>

          {/* Execution Friction */}
          <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-400">
            <div>
              <span>Brokerage (bps)</span>
              <div className="text-white font-bold mt-0.5">{(transactionCost * 10000).toFixed(0)} bps</div>
            </div>
            <div>
              <span>Slippage (bps)</span>
              <div className="text-white font-bold mt-0.5">{(slippage * 10000).toFixed(0)} bps</div>
            </div>
          </div>

          <button
            onClick={handleRunBacktest}
            disabled={backtestMutation.isPending}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-cyan-600 to-sky-500 hover:from-cyan-500 hover:to-sky-400 text-slate-950 font-mono font-bold text-xs shadow-md transition-all disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${backtestMutation.isPending ? 'animate-spin' : ''}`} />
            <span>{backtestMutation.isPending ? 'Simulating Strategy...' : 'Execute Backtest'}</span>
          </button>
        </div>

        {/* Right 3 Columns: Backtest Performance Dashboard */}
        <div className="lg:col-span-3 space-y-6">
          {activeBacktest ? (
            <>
              {/* Scorecard KPI Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-mono">
                <div className="bg-[#0e1526]/80 border border-slate-800/80 p-3 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase">Strategy Return</div>
                  <div
                    className={`text-lg font-bold mt-1 ${
                      activeBacktest.total_return >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {activeBacktest.total_return >= 0 ? '+' : ''}
                    {activeBacktest.total_return.toFixed(2)}%
                  </div>
                  <div className="text-[9px] text-slate-500">
                    Bench: {activeBacktest.benchmark_return ? `${activeBacktest.benchmark_return.toFixed(1)}%` : '—'}
                  </div>
                </div>

                <div className="bg-[#0e1526]/80 border border-slate-800/80 p-3 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase">CAGR</div>
                  <div className="text-lg font-bold text-white mt-1">
                    {activeBacktest.cagr ? `${activeBacktest.cagr.toFixed(2)}%` : '—'}
                  </div>
                  <div className="text-[9px] text-slate-500">Annualized</div>
                </div>

                <div className="bg-[#0e1526]/80 border border-slate-800/80 p-3 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase">Sharpe Ratio</div>
                  <div className="text-lg font-bold text-cyan-400 mt-1">
                    {activeBacktest.sharpe_ratio ? activeBacktest.sharpe_ratio.toFixed(2) : '—'}
                  </div>
                  <div className="text-[9px] text-slate-500">Rf = 6.0% (India)</div>
                </div>

                <div className="bg-[#0e1526]/80 border border-slate-800/80 p-3 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase">Max Drawdown</div>
                  <div className="text-lg font-bold text-rose-400 mt-1">
                    {activeBacktest.max_drawdown ? `${activeBacktest.max_drawdown.toFixed(2)}%` : '0.00%'}
                  </div>
                  <div className="text-[9px] text-slate-500">Peak-to-Trough</div>
                </div>

                <div className="bg-[#0e1526]/80 border border-slate-800/80 p-3 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase">Win Rate</div>
                  <div className="text-lg font-bold text-emerald-400 mt-1">
                    {activeBacktest.win_rate ? `${activeBacktest.win_rate.toFixed(1)}%` : '—'}
                  </div>
                  <div className="text-[9px] text-slate-500">{activeBacktest.total_trades} Total Trades</div>
                </div>

                <div className="bg-[#0e1526]/80 border border-slate-800/80 p-3 rounded-xl">
                  <div className="text-[10px] text-slate-400 uppercase">Profit Factor</div>
                  <div className="text-lg font-bold text-amber-400 mt-1">
                    {activeBacktest.profit_factor ? activeBacktest.profit_factor.toFixed(2) : '—'}
                  </div>
                  <div className="text-[9px] text-slate-500">Gross Gain / Loss</div>
                </div>
              </div>

              {/* Equity Curve vs Benchmark Chart */}
              <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5">
                <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800">
                  <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                    Mark-to-Market Equity Curve vs Buy & Hold Benchmark
                  </span>
                  <div className="flex items-center gap-4 text-xs font-mono">
                    <span className="text-cyan-400 font-bold">• Sentiment Strategy</span>
                    <span className="text-slate-400">• Buy & Hold Benchmark</span>
                  </div>
                </div>

                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={activeBacktest.equity_curve} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis
                        dataKey="date"
                        stroke="#64748b"
                        fontSize={11}
                        tickFormatter={(val) => val.slice(5)}
                      />
                      <YAxis
                        domain={['auto', 'auto']}
                        stroke="#64748b"
                        fontSize={11}
                        tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }}
                        formatter={(val: any, name: any) => [`₹${Number(val).toLocaleString()}`, name]}
                      />
                      <Line
                        type="monotone"
                        dataKey="strategy_equity"
                        stroke="#38bdf8"
                        strokeWidth={2.5}
                        dot={false}
                        name="Strategy Equity"
                      />
                      <Line
                        type="monotone"
                        dataKey="benchmark_equity"
                        stroke="#64748b"
                        strokeWidth={1.5}
                        strokeDasharray="4 4"
                        dot={false}
                        name="Benchmark (Buy & Hold)"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Drawdown Series Chart */}
              {activeBacktest.drawdown_series && (
                <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
                    <span className="text-xs font-mono font-bold text-rose-400 uppercase tracking-wider">
                      Underwater Drawdown Profile (%)
                    </span>
                  </div>
                  <div className="h-36 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={activeBacktest.drawdown_series} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="date" stroke="#64748b" fontSize={10} tickFormatter={(val) => val.slice(5)} />
                        <YAxis stroke="#64748b" fontSize={10} tickFormatter={(val) => `${val}%`} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px' }}
                          formatter={(val: any) => [`${val}%`, 'Drawdown']}
                        />
                        <Area type="monotone" dataKey="drawdown" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.3} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-12 text-center text-slate-500 font-mono text-xs">
              No backtest selected. Choose a stock and click "Execute Backtest".
            </div>
          )}
        </div>
      </div>

      {/* Trade History Ledger Table */}
      {trades.length > 0 && (
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800">
            <span className="text-xs font-mono font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
              Executed Trade History & Execution Audit ({trades.length} Trades)
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                  <th className="py-2.5 px-3">Symbol</th>
                  <th className="py-2.5 px-3">Entry Date</th>
                  <th className="py-2.5 px-3">Exit Date</th>
                  <th className="py-2.5 px-3">Shares</th>
                  <th className="py-2.5 px-3">Entry Price</th>
                  <th className="py-2.5 px-3">Exit Price</th>
                  <th className="py-2.5 px-3">Net PnL (INR)</th>
                  <th className="py-2.5 px-3">Return %</th>
                  <th className="py-2.5 px-3">Exit Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {trades.map((t, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/60 transition-colors">
                    <td className="py-2 px-3 font-bold text-white">{t.symbol}</td>
                    <td className="py-2 px-3 text-slate-400">{t.entry_date.split('T')[0]}</td>
                    <td className="py-2 px-3 text-slate-400">{t.exit_date.split('T')[0]}</td>
                    <td className="py-2 px-3">{t.shares}</td>
                    <td className="py-2 px-3">₹{t.entry_price.toFixed(2)}</td>
                    <td className="py-2 px-3">₹{t.exit_price.toFixed(2)}</td>
                    <td
                      className={`py-2 px-3 font-bold ${
                        t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {t.pnl >= 0 ? '+' : ''}₹{t.pnl.toFixed(2)}
                    </td>
                    <td
                      className={`py-2 px-3 font-bold ${
                        t.return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {t.return_pct >= 0 ? '+' : ''}
                      {t.return_pct.toFixed(2)}%
                    </td>
                    <td className="py-2 px-3 text-slate-400 text-[11px]">{t.exit_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Assumptions & Methodological Transparency Note */}
      <div className="bg-[#0a0f1d] border border-slate-800/80 rounded-xl p-4 text-xs font-mono text-slate-400 space-y-1">
        <div className="text-cyan-400 font-bold uppercase flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-cyan-400" />
          Execution Methodology & Look-Ahead Bias Safeguards
        </div>
        <p className="leading-relaxed">
          Signals generated at end of trading session $t$ are scheduled for execution at session $t+1$ Open.
          Every trade incorporates a slippage deduction of {(slippage * 10000).toFixed(0)} bps and an exchange/brokerage transaction fee of {(transactionCost * 10000).toFixed(0)} bps.
          Simulations are strictly quantitative research models and do not connect to live money trading accounts.
        </p>
      </div>
    </div>
  );
};
