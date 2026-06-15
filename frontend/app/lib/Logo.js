// HealthBridge mark: a medical cross bridging a pulse line.
export default function Logo({ className = "h-7 w-7" }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      fill="none"
      aria-hidden="true"
    >
      <rect width="32" height="32" rx="9" fill="var(--color-brand-600)" />
      {/* pulse line */}
      <path
        d="M5 17h4l2.5-5 3.5 9 3-4h9"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2">
      <Logo className="h-7 w-7" />
      <span className="text-lg font-semibold tracking-tight text-ink-900">
        Health<span className="text-brand-600">Bridge</span>
      </span>
    </span>
  );
}
