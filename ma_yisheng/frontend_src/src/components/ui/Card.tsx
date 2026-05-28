import type { HTMLAttributes } from 'react'

interface Props extends HTMLAttributes<HTMLDivElement> {
  shadow?: 'brutal' | 'brutal-sm' | 'brutal-lg' | 'brutal-red' | 'brutal-yellow' | 'brutal-cyan'
}

const shadowClass: Record<string, string> = {
  'brutal':        'shadow-brutal',
  'brutal-sm':     'shadow-brutal-sm',
  'brutal-lg':     'shadow-brutal-lg',
  'brutal-red':    'shadow-brutal-red',
  'brutal-yellow': 'shadow-brutal-yellow',
  'brutal-cyan':   'shadow-brutal-cyan',
}

export function Card({ shadow = 'brutal', className = '', children, ...props }: Props) {
  return (
    <div className={`card-brutal ${shadowClass[shadow]} ${className}`} {...props}>
      {children}
    </div>
  )
}
