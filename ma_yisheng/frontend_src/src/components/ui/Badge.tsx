const config: Record<string, { bg: string; label: string }> = {
  '高危': { bg: 'bg-brutal-red text-white',    label: '高危' },
  '中危': { bg: 'bg-brutal-yellow text-black', label: '中危' },
  '低危': { bg: 'bg-brutal-cyan text-black',   label: '低危' },
}

export function Badge({ severity }: { severity: string | undefined }) {
  const { bg, label } = config[severity ?? ''] ?? { bg: 'bg-brutal-gray text-black', label: severity ?? '未知' }
  return (
    <span className={`${bg} border-2 border-black px-2 py-0.5 text-xs font-black uppercase tracking-wider`}>
      {label}
    </span>
  )
}
