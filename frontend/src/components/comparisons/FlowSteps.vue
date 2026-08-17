<script setup lang="ts">
// M1-D 输入、商品确认、偏好和维度阶段导航。by AI.Coding

defineProps<{
  current: 0 | 1 | 2 | 3
}>()

const items = [
  { title: '商品输入', description: '创建并解析候选' },
  { title: '商品确认', description: '核对事实与 SKU' },
  { title: '购买偏好', description: '预算、场景与关注点' },
  { title: '对比维度', description: '调整重点与顺序' },
]
</script>

<template>
  <nav class="flow-steps" aria-label="对比任务进度">
    <a-steps :current="current" :items="items" responsive size="small" />
  </nav>
</template>

<style scoped>
.flow-steps {
  border-bottom: 1px solid var(--line);
  background: var(--surface);
  padding: 18px 28px 20px;
}

.flow-steps :deep(.ant-steps) {
  max-width: 760px;
  margin: 0 auto;
}

.flow-steps :deep(.ant-steps-item-title) {
  font-size: 13px;
  font-weight: 650;
}

.flow-steps :deep(.ant-steps-item-description) {
  color: var(--muted);
  font-size: 11px;
}

@media (max-width: 640px) {
  .flow-steps {
    padding: 14px 16px;
  }

  .flow-steps :deep(.ant-steps-item-description) {
    display: none;
  }
}
</style>
