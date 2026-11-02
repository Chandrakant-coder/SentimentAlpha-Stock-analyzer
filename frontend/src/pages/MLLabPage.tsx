import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BrainCircuit,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCw,
  BarChart,
  HelpCircle,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { apiClient } from '../api/client';

const ALL_FEATURES = [
  { id: 'confidence_weighted_sentiment', name: 'Weighted News Sentiment' },
  { id: 'sentiment_momentum', name: 'Sentiment Momentum (7d-14d)' },
  { id: 'sentiment_surprise', name: 'Sentiment Surprise' },
  { id: 'rolling_7d_mean', name: 'Rolling 7d Sentiment' },
  { id: 'article_count', name: 'News Article Volume' },
  { id: 'returns_1d', name: 'Daily Return (1-Day)' },
  { id: 'momentum_20d', name: 'Price Momentum (20-Day)' },
  { id: 'rsi_14', name: 'Relative Strength Index (14)' },
  { id: 'macd', name: 'MACD Trend Oscillator' },
  { id: 'volatility_20d', name: 'Rolling Volatility (20-Day)' },
  { id: 'volume_ratio', name: 'Trading Volume Ratio' },
];

export const MLLabPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [modelType, setModelType] = useState<string>('XGBoostClassifier');
  const [horizon, setHorizon] = useState<number>(5);
  const [purgeOverlap, setPurgeOverlap] = useState<boolean>(true);
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>(
    ALL_FEATURES.map((f) => f.id)
  );
  const [trainStatusMsg, setTrainStatusMsg] = useState<string | null>(null);

  const { data: models, isLoading: modelsLoading } = useQuery({
    queryKey: ['models'],
    queryFn: apiClient.getModels,
    refetchInterval: 5000,
  });

  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);

  // Set selected model to latest when loaded
  React.useEffect(() => {
    if (models && models.length > 0 && !selectedModelId) {
      setSelectedModelId(models[0].model_id);
    }
  }, [models, selectedModelId]);

  const activeModel = models?.find((m) => m.model_id === selectedModelId) || models?.[0];

  const trainMutation = useMutation({
    mutationFn: apiClient.trainModel,
    onSuccess: (data) => {
      setTrainStatusMsg(`Training initiated in background: ${data.job_id}`);
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setTimeout(() => setTrainStatusMsg(null), 5000);
    },
    onError: (err: any) => {
      setTrainStatusMsg(`Training error: ${err.response?.data?.detail || err.message}`);
    },
  });

  const handleToggleFeature = (id: string) => {
    if (selectedFeatures.includes(id)) {
      if (selectedFeatures.length > 2) {
        setSelectedFeatures(selectedFeatures.filter((f) => f !== id));
      }
    } else {
      setSelectedFeatures([...selectedFeatures, id]);
    }
  };

  const featureChartData = activeModel?.feature_importance
    ? Object.entries(activeModel.feature_importance).map(([key, val]) => ({
        feature: key.replace(/_/g, ' '),
        importance: val,
      }))
    : [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white font-mono flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-cyan-400" />
            QUANTITATIVE MACHINE LEARNING LAB
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Walk-forward purged cross-validation combining FinBERT sentiment factors and market indicators. Powered by XGBoost.
          </p>
        </div>
      </div>

      {/* Grid: Training Config & Active Model Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Col: Training Form */}
        <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-800">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              Train Prediction Model
            </span>
          </div>

          {/* Model Type */}
          <div className="space-y-1">
            <label className="text-xs font-mono text-slate-400">Model Architecture</label>
            <select
              value={modelType}
              onChange={(e) => setModelType(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg p-2 text-xs font-mono text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="XGBoostClassifier">XGBoost Classifier (Primary — Gradient Boosting)</option>
            </select>
          </div>

          {/* Prediction Horizon */}
          <div className="space-y-1">
            <label className="text-xs font-mono text-slate-400">Forward Prediction Horizon</label>
            <div className="grid grid-cols-2 gap-2 font-mono text-xs">
              <button
                type="button"
                onClick={() => setHorizon(5)}
                className={`py-2 rounded-lg border transition-all ${
                  horizon === 5
                    ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50'
                    : 'bg-slate-900 text-slate-400 border-slate-800'
                }`}
              >
                5 Trading Days
              </button>
              <button
                type="button"
                onClick={() => setHorizon(21)}
                className={`py-2 rounded-lg border transition-all ${
                  horizon === 21
                    ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50'
                    : 'bg-slate-900 text-slate-400 border-slate-800'
                }`}
              >
                21 Trading Days
              </button>
            </div>
          </div>

          {/* Purge Overlap Toggle */}
          <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800">
            <div>
              <div className="text-xs font-mono text-slate-200">Purge Overlapping Windows</div>
              <div className="text-[10px] text-slate-500 font-mono">Removes label bleed into test split</div>
            </div>
            <input
              type="checkbox"
              checked={purgeOverlap}
              onChange={(e) => setPurgeOverlap(e.target.checked)}
              className="w-4 h-4 rounded text-cyan-500 focus:ring-0 cursor-pointer accent-cyan-500"
            />
          </div>

          {/* Features Checkboxes */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono text-slate-400 flex items-center justify-between">
              <span>Features Selection</span>
              <span className="text-[10px] text-cyan-400">{selectedFeatures.length} active</span>
            </label>
            <div className="max-h-40 overflow-y-auto space-y-1 pr-1 border border-slate-800/60 rounded-lg p-2 bg-slate-900/30">
              {ALL_FEATURES.map((feat) => (
                <label
                  key={feat.id}
                  className="flex items-center gap-2 text-xs font-mono text-slate-300 hover:text-white cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedFeatures.includes(feat.id)}
                    onChange={() => handleToggleFeature(feat.id)}
                    className="w-3.5 h-3.5 rounded text-cyan-500 focus:ring-0 accent-cyan-500"
                  />
                  <span>{feat.name}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Submit Button */}
          <button
            onClick={() =>
              trainMutation.mutate({
                model_type: modelType,
                target_horizon: horizon,
                features: selectedFeatures,
                test_size: 0.2,
                purge_overlap: purgeOverlap,
              })
            }
            disabled={trainMutation.isPending}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-cyan-600 to-sky-500 hover:from-cyan-500 hover:to-sky-400 text-slate-950 font-mono font-bold text-xs shadow-md transition-all disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${trainMutation.isPending ? 'animate-spin' : ''}`} />
            <span>{trainMutation.isPending ? 'Training in Background...' : 'Launch Training Pipeline'}</span>
          </button>

          {trainStatusMsg && (
            <div className="text-xs font-mono p-2.5 rounded bg-slate-900 border border-cyan-800/60 text-cyan-300 text-center">
              {trainStatusMsg}
            </div>
          )}
        </div>

        {/* Right 2 Cols: Active Model Performance & Feature Importances */}
        <div className="lg:col-span-2 space-y-6">
          {activeModel ? (
            <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
                <div>
                  <span className="text-xs font-mono font-bold text-cyan-400">{activeModel.model_id}</span>
                  <div className="text-sm font-bold text-white mt-0.5">
                    {activeModel.model_type} • {activeModel.target_horizon}D Forward Horizon
                  </div>
                </div>
                <div className="text-[10px] font-mono text-slate-400">
                  Samples: {activeModel.train_samples} Train / {activeModel.test_samples} Test
                </div>
              </div>

              {/* Validation Metrics Scorecards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-400">Accuracy (Held-out)</div>
                  <div className="text-xl font-bold text-emerald-400 mt-1">
                    {activeModel.accuracy ? `${(activeModel.accuracy * 100).toFixed(1)}%` : '—'}
                  </div>
                </div>

                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-400">Precision</div>
                  <div className="text-xl font-bold text-cyan-400 mt-1">
                    {activeModel.precision ? `${(activeModel.precision * 100).toFixed(1)}%` : '—'}
                  </div>
                </div>

                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-400">Recall</div>
                  <div className="text-xl font-bold text-sky-400 mt-1">
                    {activeModel.recall ? `${(activeModel.recall * 100).toFixed(1)}%` : '—'}
                  </div>
                </div>

                <div className="bg-slate-900/60 border border-slate-800 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-400">ROC-AUC</div>
                  <div className="text-xl font-bold text-amber-400 mt-1">
                    {activeModel.roc_auc ? activeModel.roc_auc.toFixed(3) : '—'}
                  </div>
                </div>
              </div>

              {/* Feature Importance Bar Chart */}
              <div className="space-y-2 pt-2">
                <div className="text-xs font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Feature Importances (SHAP / Gini Relative Weight)</span>
                </div>
                <div className="h-56 w-full">
                  {featureChartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <RechartsBarChart
                        layout="vertical"
                        data={featureChartData}
                        margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                        <XAxis type="number" stroke="#64748b" fontSize={10} />
                        <YAxis type="category" dataKey="feature" stroke="#94a3b8" fontSize={10} width={110} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px' }}
                          formatter={(val: any) => [Number(val).toFixed(4), 'Importance']}
                        />
                        <Bar dataKey="importance" fill="#38bdf8" radius={[0, 4, 4, 0]} />
                      </RechartsBarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex items-center justify-center h-full text-slate-500 font-mono text-xs">
                      No feature importance weights available.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-8 text-center text-slate-500 font-mono text-xs">
              No trained models in registry. Configure and launch a training job.
            </div>
          )}
        </div>
      </div>

      {/* Model Registry History Table */}
      <div className="bg-[#0e1526]/80 border border-slate-800/80 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800">
          <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
            Model Registry & Version Comparison
          </span>
          <span className="text-xs font-mono text-slate-400">
            {models?.length || 0} Registered Artifacts
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                <th className="py-2.5 px-3">Model ID</th>
                <th className="py-2.5 px-3">Architecture</th>
                <th className="py-2.5 px-3">Horizon</th>
                <th className="py-2.5 px-3">Train / Test Samples</th>
                <th className="py-2.5 px-3">Accuracy</th>
                <th className="py-2.5 px-3">Precision</th>
                <th className="py-2.5 px-3">Recall</th>
                <th className="py-2.5 px-3">AUC</th>
                <th className="py-2.5 px-3">Trained At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {models && models.length > 0 ? (
                models.map((m) => (
                  <tr
                    key={m.model_id}
                    onClick={() => setSelectedModelId(m.model_id)}
                    className={`cursor-pointer transition-colors ${
                      selectedModelId === m.model_id ? 'bg-cyan-950/30 text-cyan-300' : 'hover:bg-slate-900/60 text-slate-200'
                    }`}
                  >
                    <td className="py-2.5 px-3 font-bold">{m.model_id}</td>
                    <td className="py-2.5 px-3 text-slate-400">{m.model_type}</td>
                    <td className="py-2.5 px-3">{m.target_horizon}D</td>
                    <td className="py-2.5 px-3 text-slate-400">{m.train_samples} / {m.test_samples}</td>
                    <td className="py-2.5 px-3 font-bold text-emerald-400">
                      {m.accuracy ? `${(m.accuracy * 100).toFixed(1)}%` : '—'}
                    </td>
                    <td className="py-2.5 px-3">{m.precision ? `${(m.precision * 100).toFixed(1)}%` : '—'}</td>
                    <td className="py-2.5 px-3">{m.recall ? `${(m.recall * 100).toFixed(1)}%` : '—'}</td>
                    <td className="py-2.5 px-3 text-amber-400">{m.roc_auc ? m.roc_auc.toFixed(3) : '—'}</td>
                    <td className="py-2.5 px-3 text-slate-500">{m.created_at.split('T')[0]}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="py-6 text-center text-slate-500">
                    No models trained yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
