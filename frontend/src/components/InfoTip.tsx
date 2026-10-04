import { Info } from 'lucide-react'
import { useId } from 'react'

interface Props {
  /** what the explanation is about, for screen readers: "About Verified evidence" */
  label: string
  text: string
  align?: 'left' | 'right'
  side?: 'top' | 'bottom'
}

/** A small information control. The explanation shows on hover and on keyboard focus. */
export function InfoTip({ label, text, align = 'left', side = 'bottom' }: Props) {
  const id = useId()
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        data-testid="info-tip"
        aria-label={`About ${label}`}
        aria-describedby={id}
        onClick={(e) => e.stopPropagation()}
        className="rounded-full p-0.5 text-slate-400 hover:text-ink focus-visible:text-ink"
      >
        <Info size={14} aria-hidden />
      </button>
      <span
        role="tooltip"
        id={id}
        className={`pointer-events-none invisible absolute z-30 w-64 rounded-md bg-ink px-3 py-2 text-left font-sans text-xs font-normal leading-relaxed text-white opacity-0 shadow-lg transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100 ${
          side === 'top' ? 'bottom-full mb-1.5' : 'top-full mt-1.5'
        } ${align === 'right' ? 'right-0' : 'left-0'}`}
      >
        {text}
      </span>
    </span>
  )
}
