import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { Activity } from '../types/api';
import SplitBreakdown from './SplitBreakdown';

interface Props {
  activity: Activity;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatDuration(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0)
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatActivityType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export default function ActivityCard({ activity }: Props) {
  const [expanded, setExpanded] = useState(false);

  const hasSplits = activity.splits.length > 0;

  return (
    <div
      className={`rounded-2xl bg-panel p-5 transition-colors ${hasSplits ? 'hover:bg-panel-light cursor-pointer' : ''}`}
      onClick={() => {
        if (hasSplits) setExpanded((v) => !v);
      }}
    >
      {/* Header: date + type badge */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-sm text-text-secondary">
            {formatDate(activity.date)}
          </span>
          <span className="rounded-full bg-panel-light px-2.5 py-0.5 text-xs font-medium text-text-muted">
            {formatActivityType(activity.activity_type)}
          </span>
        </div>
        {hasSplits && (
          <span className="text-text-muted">
            {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </span>
        )}
      </div>

      {/* Key metrics row */}
      <div className="flex flex-wrap gap-x-6 gap-y-2 mb-2">
        {activity.distance_km != null && (
          <div>
            <span className="text-xs text-text-muted uppercase tracking-wider">
              Distance
            </span>
            <p className="font-data text-lg font-semibold text-text-primary">
              {activity.distance_km.toFixed(1)}{' '}
              <span className="text-xs text-text-muted font-normal">km</span>
            </p>
          </div>
        )}
        {activity.duration_sec != null && (
          <div>
            <span className="text-xs text-text-muted uppercase tracking-wider">
              Duration
            </span>
            <p className="font-data text-lg font-semibold text-text-primary">
              {formatDuration(activity.duration_sec)}
            </p>
          </div>
        )}
        {activity.avg_power != null && (
          <div>
            <span className="text-xs text-text-muted uppercase tracking-wider">
              Avg Power
            </span>
            <p className="font-data text-lg font-semibold text-text-primary">
              {Math.round(activity.avg_power)}{' '}
              <span className="text-xs text-text-muted font-normal">W</span>
            </p>
          </div>
        )}
        {activity.avg_hr != null && (
          <div>
            <span className="text-xs text-text-muted uppercase tracking-wider">
              Avg HR
            </span>
            <p className="font-data text-lg font-semibold text-text-primary">
              {Math.round(activity.avg_hr)}{' '}
              <span className="text-xs text-text-muted font-normal">bpm</span>
            </p>
          </div>
        )}
      </div>

      {/* Secondary metrics */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-text-secondary">
        {activity.avg_pace_min_km != null && (
          <span>
            <span className="text-text-muted">Pace</span>{' '}
            <span className="font-data">{activity.avg_pace_min_km}</span>{' '}
            /km
          </span>
        )}
        {activity.elevation_gain_m != null && (
          <span>
            <span className="text-text-muted">Elev</span>{' '}
            <span className="font-data">
              {Math.round(activity.elevation_gain_m)}
            </span>{' '}
            m
          </span>
        )}
        {activity.rss != null && (
          <span>
            <span className="text-text-muted">RSS</span>{' '}
            <span className="font-data">{Math.round(activity.rss)}</span>
          </span>
        )}
        {activity.cp_estimate != null && (
          <span>
            <span className="text-text-muted">CP</span>{' '}
            <span className="font-data">{Math.round(activity.cp_estimate)}</span>{' '}
            W
          </span>
        )}
      </div>

      {/* Expandable splits */}
      {expanded && hasSplits && (
        <SplitBreakdown
          splits={activity.splits}
          cpEstimate={activity.cp_estimate}
        />
      )}
    </div>
  );
}
