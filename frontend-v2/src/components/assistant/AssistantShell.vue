<script setup lang="ts">
import { computed, ref, watch, type CSSProperties } from 'vue'
import { NButton, NDrawer, NDrawerContent, NIcon } from 'naive-ui'
import { SparklesOutline } from '@vicons/ionicons5'
import AssistantPanel from '@/components/AssistantPanel.vue'
import AssistantGreetingBubble from '@/features/overview/AssistantGreetingBubble.vue'
import { useAssistantPreferences } from '@/composables/useAssistantPreferences'
import { useAssistantLauncherPosition } from '@/composables/useAssistantLauncherPosition'
import { useLocale } from '@/composables/useLocale'

withDefaults(defineProps<{ isHome?: boolean }>(), { isHome: false })

const { t } = useLocale()
const { enabled } = useAssistantPreferences()
const {
  launcherRef,
  style: launcherStyle,
  dragging: launcherDragging,
  onPointerDown,
  onPointerMove,
  onPointerUp: finishLauncherPointer,
  onPointerCancel,
  consumeClick,
} = useAssistantLauncherPosition()
const open = ref(false)
const expanded = ref(false)
const drawerStyle = computed<CSSProperties>(() => expanded.value ? {
  maxWidth: 'calc(100vw - 48px)',
  height: 'min(800px, calc(100dvh - 48px))',
  top: 'max(24px, calc((100dvh - 800px) / 2))',
  right: 'max(24px, calc((100vw - 1060px) / 2))',
  bottom: 'auto',
  borderRadius: '18px',
  overflow: 'hidden',
} : { maxWidth: '100vw' })

function openAssistant() {
  if (enabled.value) open.value = true
}

function onLauncherClick(event: MouseEvent) {
  if (consumeClick(event)) return
  openAssistant()
}

function onLauncherPointerUp(event: PointerEvent) {
  if (finishLauncherPointer(event)) openAssistant()
}

watch(enabled, (isEnabled) => {
  if (!isEnabled) open.value = false
})
</script>

<template>
  <div v-if="enabled" class="assistant-shell" data-testid="assistant-shell">
    <NDrawer
      v-model:show="open"
      placement="right"
      :width="expanded ? 'min(1060px, calc(100vw - 48px))' : 440"
      :style="drawerStyle"
      :aria-label="t('assistantTitle')"
      class="assistant-shell-drawer"
      :class="{ 'assistant-shell-expanded': expanded }"
    >
      <NDrawerContent :native-scrollbar="false" body-content-style="padding: 0; height: 100%;">
        <AssistantPanel :expanded="expanded" @toggle-expanded="expanded = !expanded" @close="open = false" />
      </NDrawerContent>
    </NDrawer>

    <AssistantGreetingBubble v-if="isHome" @open="openAssistant" />
    <NButton
      ref="launcherRef"
      class="assistant-shell-fab"
      :class="{ 'assistant-shell-fab-dragging': launcherDragging }"
      data-testid="assistant-shell-fab"
      :style="launcherStyle"
      circle
      :aria-label="t('toggleAssistant')"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onLauncherPointerUp"
      @pointercancel="onPointerCancel"
      @lostpointercapture="onPointerCancel"
      @click="onLauncherClick"
    >
      <template #icon><NIcon :component="SparklesOutline" size="20" /></template>
    </NButton>
  </div>
</template>

<style scoped>
.assistant-shell {
  position: relative;
  z-index: 80;
  --assistant-shell-entry-bottom: calc(24px + env(safe-area-inset-bottom));
}

.assistant-shell-drawer :deep(.n-drawer-content),
.assistant-shell-drawer :deep(.n-drawer-body),
.assistant-shell-drawer :deep(.n-drawer-body-content-wrapper) {
  height: 100%;
  padding: 0;
}

.assistant-shell-drawer :deep(.n-drawer-header) {
  display: none;
}

.assistant-shell-fab {
  position: fixed;
  right: 18px;
  bottom: var(--assistant-shell-entry-bottom);
  z-index: 80;
  width: 48px;
  height: 48px;
  border: 1px solid color-mix(in srgb, var(--df-accent-strong) 62%, var(--df-border-soft));
  color: var(--df-accent-strong);
  background: var(--df-surface-2);
  box-shadow: var(--df-shadow);
  cursor: grab;
  touch-action: none;
}

.assistant-shell-fab-dragging {
  cursor: grabbing;
}

.assistant-shell-fab:hover {
  border-color: var(--df-interactive-strong);
  color: var(--df-interactive-strong);
}

/* The owner play surface has a bottom composer on narrow screens. Keep the
   global entry above that operation area while preserving a comfortable tap
   target on the rest of the app. */
@media (max-width: 800px) {
  .assistant-shell {
    --assistant-shell-entry-bottom: calc(76px + env(safe-area-inset-bottom));
  }

  .assistant-shell-fab {
    right: 14px;
    bottom: var(--assistant-shell-entry-bottom);
    width: 44px;
    height: 44px;
  }

  :global(.app-shell-play) .assistant-shell-fab {
    bottom: calc(92px + env(safe-area-inset-bottom));
  }

  :global(.app-shell-play) .assistant-shell {
    --assistant-shell-entry-bottom: calc(92px + env(safe-area-inset-bottom));
  }
}
</style>
