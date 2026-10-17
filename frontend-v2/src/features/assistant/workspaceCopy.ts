export function assistantWorkspaceCopy(locale: string) {
  return locale.startsWith('zh') ? {
    expand: '展开任务工作区', collapse: '收起任务工作区', working: '处理中', attention: '需要处理',
    drafts: (count: number) => `${count} 份草稿`,
    resetPosition: '恢复悬浮球位置', resetPositionHint: '入口被移动到难找的位置时，可将它恢复到右下角。',
  } : {
    expand: 'Expand task workspace', collapse: 'Collapse task workspace', working: 'Working', attention: 'Needs attention',
    drafts: (count: number) => `${count} ${count === 1 ? 'draft' : 'drafts'}`,
    resetPosition: 'Reset launcher position', resetPositionHint: 'Return the launcher to the bottom right if it becomes difficult to find.',
  }
}
