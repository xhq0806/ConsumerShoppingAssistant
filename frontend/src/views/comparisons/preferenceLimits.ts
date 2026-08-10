export function limitPreferenceItems(values: unknown, maximum: number): string[] {
  /** 将标签选择保持在界面声明的数量上限内。by AI.Coding */
  if (!Array.isArray(values)) {
    return []
  }
  return values.filter((value): value is string => typeof value === 'string').slice(0, maximum)
}
