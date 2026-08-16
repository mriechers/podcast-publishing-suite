import { useEffect, useState } from 'react'

/**
 * Debounces a value by delaying updates until the value has stopped changing
 * for the specified delay period.
 *
 * @param value - The value to debounce
 * @param delay - Delay in milliseconds (default: 300ms)
 * @returns The debounced value
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    // Set up timer to update debounced value after delay
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    // Cleanup: cancel timer if value changes before delay elapses
    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return debouncedValue
}
