import { CircleHelp, GitCompare, Shield, ShieldAlert, ShieldCheck, type LucideIcon } from 'lucide-react'
import type { EvidenceState } from '../api/types'

// The state is always shown as icon + words; colour is never the only signal and there are no percentages.
const STATES: Record<EvidenceState, { label: string; style: string; Icon: LucideIcon }> = {
  HIGH: { label: 'Strong evidence', style: 'bg-green-100 text-green-900 border-green-300', Icon: ShieldCheck },
  MEDIUM: { label: 'Moderate evidence', style: 'bg-blue-100 text-blue-900 border-blue-300', Icon: Shield },
  LOW: { label: 'Weak evidence', style: 'bg-amber-100 text-amber-900 border-amber-300', Icon: ShieldAlert },
  CONFLICT: { label: 'Conflict detected', style: 'bg-red-100 text-red-900 border-red-300', Icon: GitCompare },
  INSUFFICIENT: { label: 'Insufficient evidence', style: 'bg-slate-100 text-slate-800 border-slate-300', Icon: CircleHelp },
}

export function StateBadge({ state }: { state: EvidenceState }) {
  const { label, style, Icon } = STATES[state]
  return (
    <span
      data-testid="state-badge"
      data-state={state}
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-semibold ${style}`}
    >
      <Icon size={14} aria-hidden />
      {label}
    </span>
  )
}
