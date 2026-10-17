import { computed, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/** Follow the actual application header, including wrapping and theme fonts. */
export function useSectionHeaderOffset(navigation: Ref<HTMLElement | null>) {
  const height = ref(68)
  const navigationHeight = ref(56)
  let header: HTMLElement | null = null
  let observer: ResizeObserver | undefined
  const measure = () => {
    if (header) height.value = header.getBoundingClientRect().height
    if (navigation.value) navigationHeight.value = navigation.value.getBoundingClientRect().height
  }
  onMounted(() => {
    header = document.querySelector<HTMLElement>('.app-header')
    measure()
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(measure)
      if (header) observer.observe(header)
      if (navigation.value) observer.observe(navigation.value)
    }
    window.addEventListener('resize', measure)
  })
  onBeforeUnmount(() => { observer?.disconnect(); window.removeEventListener('resize', measure) })
  return computed(() => ({ '--section-header-height': `${height.value}px`, '--section-navigation-height': `${navigationHeight.value}px` }))
}
