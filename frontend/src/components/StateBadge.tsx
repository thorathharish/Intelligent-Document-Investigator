import { CircleHelp, GitCompare, Shield, ShieldAlert, ShieldCheck, type LucideIcon } from 'lucide-react'
import type { EvidenceState } from '../api/types'

// The state is always shown as icon + words; colour is never the only signal and there are no percentages.
export const STATES: Record<EvidenceState, { label: string; meaning: string; style: string; Icon: LucideIcon }> = {
  HIGH: {
    label: 'Strong evidence',
    meaning: 'Stated directly by independent documents that agree.',
    style: 'bg-emerald-50 text-emerald-900 border-emerald-300',
    Icon: ShieldCheck,
  },
  MEDIUM: {
    label: 'Moderate evidence',
    meaning: 'Supported by verified evidence, with limited corroboration.',
    style: 'bg-sky-50 text-sky-900 border-sky-300',
    Icon: Shield,
  },
  LOW: {
    label: 'Weak evidence',
    meaning: 'The evidence is limited, ambiguous, incomplete or of lower quality.',
    style: 'bg-amber-50 text-amber-900 border-amber-300',
    Icon: ShieldAlert,
  },
  CONFLICT: {
    label: 'Conflict detected',
    meaning: 'Verified evidence contains incompatible positions.',
    style: 'bg-red-50 text-red-900 border-red-300',
    Icon: GitCompare,
  },
  INSUFFICIENT: {
    label: 'Insufficient evidence',
    meaning: 'No verified evidence is sufficient to answer.',
    style: 'bg-slate-100 text-slate-800 border-slate-300',
    Icon: CircleHelp,
  },
}

export function StateBadge({ state, compact = false }: { state: EvidenceState; compact?: boolean }) {
  const { label, style, Icon } = STATES[state]
  return (
    <span
      data-testid="state-badge"
      data-state={state}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border font-semibold ${style} ${
        compact ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'
      }`}
    >
      <Icon size={compact ? 13 : 16} aria-hidden />
      {label}
    </span>
  )
}
