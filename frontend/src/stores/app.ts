import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({ milestone: 'M0' }),
})
