import type { ButtonHTMLAttributes } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'yellow' | 'red' | 'cyan' | 'purple' | 'white' | 'black'
  size?: 'sm' | 'md' | 'lg'
}

const variantClass: Record<string, string> = {
  yellow: 'bg-brutal-yellow text-black',
  red:    'bg-brutal-red text-white',
  cyan:   'bg-brutal-cyan text-black',
  purple: 'bg-brutal-purple text-white',
  white:  'bg-white text-black',
  black:  'bg-black text-white',
}

const sizeClass: Record<string, string> = {
  sm: 'px-3 py-1 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export function Button({ variant = 'yellow', size = 'md', className = '', children, ...props }: Props) {
  return (
    <button
      className={`btn-brutal ${variantClass[variant]} ${sizeClass[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
