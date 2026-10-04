import { CircleHelp, GitCompare, Shield, ShieldAlert, ShieldCheck, type LucideIcon } from 'lucide-react'
import type { EvidenceState } from '../api/types'

// The state name is primary and its plain-language label secondary. Colour is never the only signal
// and there are no percentages.
export const STATES: Record<
  EvidenceState,
  { label: string; help: string; meaning: string; style: string; dot: string; Icon: LucideIcon }
> = {
  HIGH: {
    label: 'Strong evidence',
    help: 'Strong evidence: the relevant claim is explicitly supported by independent verified sources.',
    meaning: 'Stated directly by independent documents that agree.',
    style: 'bg-emerald-50 text-emerald-900 border-emerald-300',
    dot: 'bg-emerald-600',
    Icon: ShieldCheck,
  },
  MEDIUM: {
    label: 'Moderate evidence',
    help: 'Moderate evidence: verified evidence supports the answer, but corroboration or coverage is limited.',
    meaning: 'Supported by verified evidence, with limited corroboration.',
    style: 'bg-sky-50 text-sky-900 border-sky-300',
    dot: 'bg-sky-600',
    Icon: Shield,
  },
  LOW: {
    label: 'Limited evidence',
    help: 'Limited evidence: the available evidence is incomplete, ambiguous, or otherwise insufficient for strong confidence.',
    meaning: 'The evidence is limited, ambiguous, incomplete or of lower quality.',
    style: 'bg-amber-50 text-amber-900 border-amber-300',
    dot: 'bg-amber-500',
    Icon: ShieldAlert,
  },
  CONFLICT: {
    label: 'Evidence disagrees',
    help: 'Conflicting evidence: verified documents support different positions.',
    meaning: 'Verified evidence contains incompatible positions.',
    style: 'bg-red-50 text-red-900 border-red-300',
    dot: 'bg-red-600',
    Icon: GitCompare,
  },
  INSUFFICIENT: {
    label: 'Insufficient evidence',
    help: 'Insufficient evidence: the available verified documents do not contain enough evidence to answer reliably.',
    meaning: 'No verified evidence is sufficient to answer.',
    style: 'bg-slate-100 text-slate-800 border-slate-300',
    dot: 'bg-slate-500',
    Icon: CircleHelp,
  },
}

export function StateBadge({ state }: { state: EvidenceState }) {
  const { label, style, Icon } = STATES[state]
  return (
    <span
      data-testid="state-badge"
      data-state={state}
      className={`inline-flex shrink-0 items-center gap-2 rounded-md border px-2.5 py-1 text-sm ${style}`}
    >
      <Icon size={16} aria-hidden />
      <span className="font-bold tracking-wide">{state}</span>
      <span className="border-l border-current/30 pl-2">{label}</span>
    </span>
  )
}

/** Compact form for history rows: a coloured dot plus the state name. */
export function StateTag({ state }: { state: EvidenceState }) {
  return (
    <span className="inline-flex w-28 shrink-0 items-center gap-1.5 text-xs font-semibold" title={STATES[state].label}>
      <span className={`h-2 w-2 rounded-full ${STATES[state].dot}`} aria-hidden />
      {state}
    </span>
  )
}
