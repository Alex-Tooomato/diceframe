<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'

defineProps<{ label: string }>()
const panelId = useId()
const open = ref(false)
const root = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
const panel = ref<HTMLElement>()

async function toggle() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    panel.value?.querySelector<HTMLElement>('button:not(:disabled), a[href], select')?.focus()
  }
}
function escape(event: KeyboardEvent) {
  if (event.key !== 'Escape' || !open.value) return
  event.preventDefault()
  event.stopPropagation()
  open.value = false
  trigger.value?.focus()
}
function outside(event: Event) {
  if (event.target instanceof Node && !root.value?.contains(event.target)) open.value = false
}
function selected(event: MouseEvent) {
  if ((event.target as Element).closest('button, a[href]')) open.value = false
}
onMounted(() => document.addEventListener('pointerdown', outside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside))
</script>

<template>
  <div ref="root" class="play-utility-menu" @keydown="escape">
    <button ref="trigger" type="button" data-testid="play-tools-toggle" :aria-expanded="open" :aria-controls="panelId" @click="toggle">
      <span>{{ label }}</span><span aria-hidden="true">⌄</span>
    </button>
    <div v-if="open" :id="panelId" ref="panel" class="play-utility-panel" data-testid="play-tools-panel" @click="selected">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.play-utility-menu { position: relative; flex: 0 0 auto; }
.play-utility-menu > button { display: inline-flex; align-items: center; gap: 8px; }
.play-utility-panel { position: absolute; z-index: 68; inset: calc(100% + 6px) 0 auto auto; display: grid; gap: 4px; width: min(230px, calc(100vw - 24px)); padding: 8px; border: 1px solid var(--df-border-soft); border-radius: 8px; background: var(--df-surface-1); box-shadow: var(--df-shadow); }
.play-utility-panel :deep(button) { width: 100%; min-height: 40px; margin: 0; text-align: start; justify-content: start; white-space: normal; }
@media (max-width: 800px) { .play-utility-menu > button, .play-utility-panel :deep(button) { min-height: 44px; } }
</style>
