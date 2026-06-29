import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Report } from '../api/reports'
import type { Task } from '../api/scan'

export type ScanTab = 'upload' | 'path'

export interface ScanFormState {
  tab: ScanTab
  path: string
  engine: string
  lang: string
  scene: string
  timeout: string
  ruleSetIds: number[]
}

interface PageState {
  scanForm: ScanFormState
  reportsSearch: string
  reports: Report[]
  reportsLoaded: boolean
  tasks: Task[]
  tasksLoaded: boolean
  setScanForm: (patch: Partial<ScanFormState>) => void
  resetScanInput: () => void
  setReportsState: (patch: Partial<Pick<PageState, 'reportsSearch' | 'reports' | 'reportsLoaded'>>) => void
  setTasksState: (patch: Partial<Pick<PageState, 'tasks' | 'tasksLoaded'>>) => void
}

export const usePageStateStore = create<PageState>()(
  persist(
    (set) => ({
      scanForm: {
        tab: 'path',
        path: '',
        engine: 'yasa',
        lang: 'python',
        scene: 'full',
        timeout: '1800',
        ruleSetIds: [],
      },
      reportsSearch: '',
      reports: [],
      reportsLoaded: false,
      tasks: [],
      tasksLoaded: false,
      setScanForm: (patch) => set((state) => ({ scanForm: { ...state.scanForm, ...patch } })),
      resetScanInput: () => set((state) => ({ scanForm: { ...state.scanForm, path: '' } })),
      setReportsState: (patch) => set(patch),
      setTasksState: (patch) => set(patch),
    }),
    {
      name: 'ma-yisheng-page-state',
      partialize: (state) => ({
        scanForm: state.scanForm,
        reportsSearch: state.reportsSearch,
        reports: state.reports,
        reportsLoaded: state.reportsLoaded,
        tasks: state.tasks,
        tasksLoaded: state.tasksLoaded,
      }),
    },
  ),
)
