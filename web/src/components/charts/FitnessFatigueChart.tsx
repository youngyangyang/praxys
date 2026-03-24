import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from 'recharts';
import type { TimeSeriesData } from '../../types/api';

interface Props {
  data: TimeSeriesData;
}

export default function FitnessFatigueChart({ data }: Props) {
  const chartData = data.dates.map((date, i) => ({
    date,
    ctl: data.ctl[i],
    atl: data.atl[i],
    tsb: data.tsb[i],
  }));

  return (
    <div className="rounded-2xl bg-panel p-5 sm:p-6">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-4">
        Fitness / Fatigue / Form
      </h3>
      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickFormatter={(v: string) => v.slice(5)}
            interval={Math.max(0, Math.floor(chartData.length / 7) - 1)}
          />
          <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 8,
            }}
            labelStyle={{ color: '#94a3b8' }}
          />
          <Area
            type="monotone"
            dataKey="tsb"
            fill="#3b82f6"
            fillOpacity={0.1}
            stroke="none"
          />
          <Line
            type="monotone"
            dataKey="ctl"
            stroke="#00ff87"
            strokeWidth={2}
            dot={false}
            name="CTL (Fitness)"
          />
          <Line
            type="monotone"
            dataKey="atl"
            stroke="#ef4444"
            strokeWidth={2}
            dot={false}
            name="ATL (Fatigue)"
          />
          <Line
            type="monotone"
            dataKey="tsb"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="TSB (Form)"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
