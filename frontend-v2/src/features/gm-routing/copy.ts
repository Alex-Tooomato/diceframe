import type { Locale } from '@/i18n'

export interface GmRoutingCopy {
  title: string
  serverMode: string
  serverModeHint: string
  userMode: string
  userModeHint: string
  provider: string
  model: string
  roleMain: string
  roleFallback1: string
  roleFallback2: string
  roleCheck: string
  checkFollowMain: string
  followServer: string
  followServerHint: string
  inheritServer: string
  save: string
  cancel: string
  reload: string
  loading: string
  error: string
  stale: string
  configure: string
  effectiveTitle: string
  effectiveServer: string
  effectiveUser: string
  online: string
  offline: string
  offlineHint: string
  applicationModel: string
  serverFallbackReady: string
  serverFallbackOff: string
  unavailable: string
  mainRequired: string
  reasonGmOffline: string
  reasonModelUnavailable: string
  reasonUnsupported: string
  reasonProviderMissing: string
  reasonProviderUnconfigured: string
  reasonModelMissing: string
  reasonModelNotChat: string
  reasonModelRequired: string
}

const en: GmRoutingCopy = {
  title: 'GM source', serverMode: 'Server GM', serverModeHint: 'Use the main model configured on this server for every GM call.',
  userMode: 'User GM (this seat)', userModeHint: 'Your own model drives this game while you are connected; the server model takes over when you leave.',
  provider: 'Provider', model: 'Model', roleMain: 'Main model', roleFallback1: 'Fallback 1', roleFallback2: 'Fallback 2',
  roleCheck: 'Check model', checkFollowMain: 'Follow main model', followServer: 'Fall back to the server model',
  followServerHint: 'When your models fail or you disconnect, the server main model keeps the game running.',
  inheritServer: 'Inherit server setting', save: 'Save', cancel: 'Cancel', reload: 'Reload', loading: 'Loading…',
  error: 'Could not load or save GM routing. Reload and try again.', stale: 'Settings changed elsewhere. Reload and retry.',
  configure: 'Configure', effectiveTitle: 'Current GM',
  effectiveServer: 'Server model', effectiveUser: 'Your model', online: 'online', offline: 'offline',
  offlineHint: 'You are offline: the server GM is hosting this game.',
  applicationModel: 'Server main model', serverFallbackReady: 'Server fallback active', serverFallbackOff: 'Server fallback disabled',
  unavailable: 'Unavailable', mainRequired: 'Choose a main model for user GM mode.',
  reasonGmOffline: 'User GM offline — using the server model',
  reasonModelUnavailable: 'No GM model available; reconnect or fix the configuration',
  reasonUnsupported: 'Saved routing is not supported by this server',
  reasonProviderMissing: 'Provider missing', reasonProviderUnconfigured: 'Provider unconfigured',
  reasonModelMissing: 'Model removed from provider catalog', reasonModelNotChat: 'Model does not support chat',
  reasonModelRequired: 'Choose a model',
}

const zh: GmRoutingCopy = {
  title: 'GM 来源', serverMode: '服务端 GM', serverModeHint: '所有 GM 调用使用服务端配置的主模型。',
  userMode: 'user GM（本席位）', userModeHint: '你在线时由你选择的模型主持本局；你离线后自动切回服务端模型。',
  provider: '服务商', model: '模型', roleMain: '主模型', roleFallback1: '备用模型 1', roleFallback2: '备用模型 2',
  roleCheck: '独立检定模型', checkFollowMain: '跟随主模型', followServer: '允许回退服务端模型',
  followServerHint: '你的模型失效或掉线时，服务端主模型会接管对局，避免中断。',
  inheritServer: '继承服务端设置', save: '保存', cancel: '取消', reload: '重新加载', loading: '加载中…',
  error: 'GM 路由读取或保存失败，请重新加载后重试。', stale: '配置已被其他会话修改，请重新加载后再试。',
  configure: '配置', effectiveTitle: '当前 GM',
  effectiveServer: '服务端模型', effectiveUser: '你的模型', online: '在线', offline: '离线',
  offlineHint: '你当前离线：本局正由服务端 GM 主持。',
  applicationModel: '服务端主模型', serverFallbackReady: '服务端兜底已启用', serverFallbackOff: '服务端兜底已关闭',
  unavailable: '不可用', mainRequired: 'user GM 模式必须选择主模型。',
  reasonGmOffline: 'user GM 离线，正在使用服务端模型',
  reasonModelUnavailable: '暂无可用 GM 模型，请重新连接或修复配置',
  reasonUnsupported: '存档中的路由配置不受当前服务端支持',
  reasonProviderMissing: '服务商引用失效', reasonProviderUnconfigured: '服务商尚未配置',
  reasonModelMissing: '模型已从服务商目录移除', reasonModelNotChat: '该模型不支持对话',
  reasonModelRequired: '请选择模型',
}

const ja: GmRoutingCopy = {
  title: 'GM の来源', serverMode: 'サーバー GM', serverModeHint: 'すべての GM 呼び出しでサーバー設定のメインモデルを使用します。',
  userMode: 'user GM（この席）', userModeHint: '接続中は選択したモデルが進行し、切断するとサーバーモデルに交代します。',
  provider: 'プロバイダー', model: 'モデル', roleMain: 'メインモデル', roleFallback1: '予備 1', roleFallback2: '予備 2',
  roleCheck: '判定モデル', checkFollowMain: 'メインに従う', followServer: 'サーバーモデルへフォールバック',
  followServerHint: 'モデルの失敗や切断時、サーバーのメインモデルがゲームを継続します。',
  inheritServer: 'サーバー設定を継承', save: '保存', cancel: 'キャンセル', reload: '再読込', loading: '読込中…',
  error: 'GM ルーティングの読み込みまたは保存に失敗しました。再読込して再試行してください。',
  stale: '設定が別のセッションで変更されました。再読込して再試行してください。',
  configure: '設定', effectiveTitle: '現在の GM',
  effectiveServer: 'サーバーモデル', effectiveUser: 'あなたのモデル', online: 'オンライン', offline: 'オフライン',
  offlineHint: '現在オフラインのため、サーバー GM が進行しています。',
  applicationModel: 'サーバーのメインモデル', serverFallbackReady: 'サーバーフォールバック有効', serverFallbackOff: 'サーバーフォールバック無効',
  unavailable: '利用不可', mainRequired: 'user GM モードではメインモデルを選択してください。',
  reasonGmOffline: 'user GM がオフラインのためサーバーモデルを使用中',
  reasonModelUnavailable: '利用できる GM モデルがありません。再接続または設定を修正してください',
  reasonUnsupported: '保存されたルーティングはこのサーバーで未対応です',
  reasonProviderMissing: 'プロバイダーが見つかりません', reasonProviderUnconfigured: 'プロバイダー未設定',
  reasonModelMissing: 'モデルが一覧から削除されています', reasonModelNotChat: 'チャット非対応モデル',
  reasonModelRequired: 'モデルを選択してください',
}

const de: GmRoutingCopy = {
  title: 'GM-Quelle', serverMode: 'Server-GM', serverModeHint: 'Alle GM-Aufrufe nutzen das auf dem Server konfigurierte Hauptmodell.',
  userMode: 'User-GM (dieser Platz)', userModeHint: 'Während du verbunden bist, leitet dein Modell; beim Verlassen übernimmt das Servermodell.',
  provider: 'Anbieter', model: 'Modell', roleMain: 'Hauptmodell', roleFallback1: 'Ersatz 1', roleFallback2: 'Ersatz 2',
  roleCheck: 'Prüfungsmodell', checkFollowMain: 'Wie Hauptmodell', followServer: 'Auf Servermodell zurückfallen',
  followServerHint: 'Wenn deine Modelle fehlschlagen oder du disconnectest, führt das Server-Hauptmodell weiter.',
  inheritServer: 'Servereinstellung übernehmen', save: 'Speichern', cancel: 'Abbrechen', reload: 'Neu laden', loading: 'Wird geladen…',
  error: 'GM-Routing konnte nicht geladen oder gespeichert werden. Neu laden und erneut versuchen.',
  stale: 'Einstellungen wurden anderswo geändert. Neu laden und erneut versuchen.',
  configure: 'Konfigurieren', effectiveTitle: 'Aktueller GM',
  effectiveServer: 'Servermodell', effectiveUser: 'Dein Modell', online: 'online', offline: 'offline',
  offlineHint: 'Du bist offline: Der Server-GM leitet dieses Spiel.',
  applicationModel: 'Server-Hauptmodell', serverFallbackReady: 'Server-Fallback aktiv', serverFallbackOff: 'Server-Fallback deaktiviert',
  unavailable: 'Nicht verfügbar', mainRequired: 'Wähle im User-GM-Modus ein Hauptmodell.',
  reasonGmOffline: 'User-GM offline – Servermodell wird verwendet',
  reasonModelUnavailable: 'Kein GM-Modell verfügbar; verbinde dich erneut oder korrigiere die Konfiguration',
  reasonUnsupported: 'Gespeichertes Routing wird von diesem Server nicht unterstützt',
  reasonProviderMissing: 'Anbieter fehlt', reasonProviderUnconfigured: 'Anbieter nicht konfiguriert',
  reasonModelMissing: 'Modell aus Anbieterliste entfernt', reasonModelNotChat: 'Modell unterstützt keinen Chat',
  reasonModelRequired: 'Modell wählen',
}

const ru: GmRoutingCopy = {
  title: 'Источник GM', serverMode: 'GM сервера', serverModeHint: 'Все вызовы GM используют главную модель, настроенную на сервере.',
  userMode: 'user GM (это место)', userModeHint: 'Пока вы на связи, игру ведёт ваша модель; при отключении принимает модель сервера.',
  provider: 'Провайдер', model: 'Модель', roleMain: 'Основная модель', roleFallback1: 'Резерв 1', roleFallback2: 'Резерв 2',
  roleCheck: 'Модель проверок', checkFollowMain: 'Как основная', followServer: 'Откат к модели сервера',
  followServerHint: 'Если ваши модели недоступны или вы отключились, игру продолжит основная модель сервера.',
  inheritServer: 'Наследовать настройки сервера', save: 'Сохранить', cancel: 'Отмена', reload: 'Обновить', loading: 'Загрузка…',
  error: 'Не удалось загрузить или сохранить маршрутизацию GM. Обновите и повторите.',
  stale: 'Настройки изменены в другом сеансе. Обновите и повторите.',
  configure: 'Настроить', effectiveTitle: 'Текущий GM',
  effectiveServer: 'Модель сервера', effectiveUser: 'Ваша модель', online: 'онлайн', offline: 'офлайн',
  offlineHint: 'Вы офлайн: игру ведёт GM сервера.',
  applicationModel: 'Главная модель сервера', serverFallbackReady: 'Резерв сервера включён', serverFallbackOff: 'Резерв сервера выключен',
  unavailable: 'Недоступно', mainRequired: 'В режиме user GM выберите основную модель.',
  reasonGmOffline: 'user GM офлайн — используется модель сервера',
  reasonModelUnavailable: 'Нет доступной модели GM; переподключитесь или исправьте настройки',
  reasonUnsupported: 'Сохранённая маршрутизация не поддерживается сервером',
  reasonProviderMissing: 'Провайдер отсутствует', reasonProviderUnconfigured: 'Провайдер не настроен',
  reasonModelMissing: 'Модель удалена из каталога', reasonModelNotChat: 'Модель не поддерживает чат',
  reasonModelRequired: 'Выберите модель',
}

export const gmRoutingCopy: Record<Locale, GmRoutingCopy> = {
  en, 'zh-CN': zh, ja, de, ru,
}

/** 运行时 reason 码 → 用户可读说明。 */
export function gmRoutingReason(copy: GmRoutingCopy, reason: string): string {
  if (!reason) return ''
  if (reason === 'gm_offline') return copy.reasonGmOffline
  if (reason === 'model_unavailable') return copy.reasonModelUnavailable
  if (reason === 'unsupported_settings') return copy.reasonUnsupported
  const code = reason.startsWith('main_') ? reason.slice(5) : reason
  if (code === 'provider_missing') return copy.reasonProviderMissing
  if (code === 'provider_unconfigured') return copy.reasonProviderUnconfigured
  if (code === 'model_missing') return copy.reasonModelMissing
  if (code === 'model_not_chat') return copy.reasonModelNotChat
  if (code === 'model_required') return copy.reasonModelRequired
  return copy.unavailable
}
