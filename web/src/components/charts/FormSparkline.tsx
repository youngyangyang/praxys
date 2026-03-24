import {
  AreaChart,
  Area,
  ResponsiveContainer,
  ReferenceLine,
  Tooltip,
  XAxis,
} from 'recharts';
import type { TsbSparkline } from '../../types/api';

interface Props {
  data: TsbSparkline;
}

export default function FormSparkline({ data }: Props) {
  const chartData = data.dates.map((date, i) => ({
    date,
    tsb: data.values[i],
  }));

  return (
    <div className="rounded-2xl bg-panel p-5 sm:p-6">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
        Form (TSB) &mdash; Last 14 Days
      </h3>
      <div style={{ width: '100%', height: 200 }}>
        <ResponsiveContainer>
          <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
            <defs>
              <linearGradient id="tsbGreen" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#00ff87" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#00ff87" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="tsbRed" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#6b7280' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: string) => v.slice(5)} // MM-DD
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1a1a2e',
                border: '1px solid #2a2a3e',
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: '#9ca3af' }}
              itemStyle={{ color: '#e5e7eb' }}
              formatter={(value) => [`${Number(value).toFixed(1)}`, 'TSB']}
            />
            <ReferenceLine y={0} stroke="#2a2a3e" strokeDasharray="3 3" />
            {/* Positive area (green) */}
            <Area
              type="monotone"
              dataKey="tsb"
              stroke="#00ff87"
              strokeWidth={2}
              fill="url(#tsbGreen)"
              baseValue={0}
              connectNulls
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
