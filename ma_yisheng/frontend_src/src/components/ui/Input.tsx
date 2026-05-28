import type { InputHTMLAttributes } from 'react'
import { forwardRef, useId } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export const Input = forwardRef<HTMLInputElement, Props>(({ label, className = '', id, ...props }, ref) => {
  const generatedId = useId()
  const inputId = id || generatedId

  return (
    <div className="flex flex-col gap-1 w-full">
      {label && <label htmlFor={inputId} className="text-xs font-bold uppercase tracking-wider">{label}</label>}
      <input ref={ref} id={inputId} className={`input-brutal ${className}`} {...props} />
    </div>
  )
})

Input.displayName = 'Input'
