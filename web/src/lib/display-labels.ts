import { msg } from '@lingui/core/macro';
import type { MessageDescriptor, I18n } from '@lingui/core';

/**
 * Known backend display-layer labels (from analysis/training_base.py).
 * The API returns these as plain English strings. To keep the backend
 * locale-agnostic, we translate them on the client via this map.
 *
 * Anything not in the map is returned verbatim — safe for dynamic values.
 */
const DISPLAY_LABEL_MAP: Record<string, MessageDescriptor> = {
  // Zone names (all training bases share these five)
  Recovery: msg`Recovery`,
  Endurance: msg`Endurance`,
  Tempo: msg`Tempo`,
  Threshold: msg`Threshold`,
  VO2max: msg`VO2max`,
  // Intensity metric labels
  Power: msg`Power`,
  'Heart Rate': msg`Heart Rate`,
  Pace: msg`Pace`,
  // Threshold labels
  'Critical Power': msg`Critical Power`,
  'Lactate Threshold HR': msg`Lactate Threshold HR`,
  'Threshold Pace': msg`Threshold Pace`,
  // Trend labels
  'CP Trend': msg`CP Trend`,
  'LTHR Trend': msg`LTHR Trend`,
  'Threshold Pace Trend': msg`Threshold Pace Trend`,
  // Distance labels (backend returns "Marathon", "Half Marathon", etc.)
  Marathon: msg`Marathon`,
  'Half Marathon': msg`Half Marathon`,
  '5K': msg`5K`,
  '10K': msg`10K`,
  '50K': msg`50K`,
  '50 Mile': msg`50 Mile`,
  '100K': msg`100K`,
  '100 Mile': msg`100 Mile`,
  Race: msg`Race`,
};

export function tDisplay(label: string | undefined | null, i18n: I18n): string {
  if (!label) return '';
  const descriptor = DISPLAY_LABEL_MAP[label];
  return descriptor ? i18n._(descriptor) : label;
}
