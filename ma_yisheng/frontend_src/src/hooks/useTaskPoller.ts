import { useEffect, useRef, useState } from 'react'
import { listTasks } from '../api/scan'
import { useMascotStore } from '../store/mascotStore'
import { usePageStateStore } from '../store/pageStateStore'

const POLL_INTERVAL = 3000

export function useTaskPoller(enabled = true) {
  const tasks = usePageStateStore((s) => s.tasks)
  const tasksLoaded = usePageStateStore((s) => s.tasksLoaded)
  const setTasksState = usePageStateStore((s) => s.setTasksState)
  const [loading, setLoading] = useState(!tasksLoaded)
  const setMascot = useMascotStore((s) => s.setStatus)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const runningIds = useRef<Set<string>>(new Set())

  const fetch = async () => {
    try {
      const res = await listTasks()
      const data = res.data.tasks ?? []
      setTasksState({ tasks: data, tasksLoaded: true })

      const nowRunning = new Set(
        data.filter((t) => t.status === 'running' || t.status === 'pending').map((t) => t.task_id)
      )

      // 检测是否有任务刚完成（之前 running 现在 done）
      let justFinished = false
      for (const id of runningIds.current) {
        const task = data.find((t) => t.task_id === id)
        if (task && (task.status === 'done' || task.status === 'completed')) {
          justFinished = true
          break
        }
      }

      const hasRunning = nowRunning.size > 0

      if (hasRunning) {
        setMascot('scanning')
      } else if (justFinished) {
        setMascot('found')
      } else {
        setMascot('idle')
      }

      runningIds.current = nowRunning
    } catch {
      // 静默失败，不影响 UI
    }
  }

  const refresh = async () => {
    setLoading(true)
    await fetch()
    setLoading(false)
  }

  useEffect(() => {
    if (!enabled) return
    fetch()
    timerRef.current = setInterval(fetch, POLL_INTERVAL)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [enabled])

  return { tasks, loading, refresh }
}
