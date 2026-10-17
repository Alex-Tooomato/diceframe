import { ref } from 'vue'

export const ASSISTANT_ENABLED_STORAGE_KEY = 'diceframe_assistant_enabled'

function readEnabled(): boolean {
  try {
    return localStorage.getItem(ASSISTANT_ENABLED_STORAGE_KEY) !== '0'
  } catch {
    return true
  }
}

const enabled = ref(readEnabled())

function setEnabled(value: boolean): void {
  enabled.value = value
  try {
    localStorage.setItem(ASSISTANT_ENABLED_STORAGE_KEY, value ? '1' : '0')
  } catch {
    // Storage is optional; the preference remains effective for this session.
  }
}

function toggle(): void {
  setEnabled(!enabled.value)
}

export function useAssistantPreferences() {
  return { enabled, setEnabled, toggle }
}
