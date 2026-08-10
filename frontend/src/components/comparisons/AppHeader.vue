<script setup lang="ts">
// M1-C 工作流统一页头。by AI.Coding

import { SafetyCertificateOutlined } from '@ant-design/icons-vue'
</script>

<template>
  <header class="app-header">
    <RouterLink class="brand-link" to="/">
      <span class="brand-mark">C</span>
      <span>
        <strong>购物决策助手</strong>
        <small>Consumer comparison workspace</small>
      </span>
    </RouterLink>
    <div class="environment-note">
      <SafetyCertificateOutlined />
      <span>Fixture 环境</span>
      <span class="environment-separator"></span>
      <span>本地开发基线</span>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  min-height: 64px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
  padding: 0 28px;
}

.brand-link {
  display: inline-flex;
  align-items: center;
  color: var(--ink);
  gap: 12px;
  text-decoration: none;
}

.brand-mark {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 6px;
  background: var(--ink);
  color: white;
  font-family: Georgia, serif;
  font-size: 20px;
}

.brand-link strong,
.brand-link small {
  display: block;
}

.brand-link strong {
  font-size: 15px;
  font-weight: 700;
}

.brand-link small {
  margin-top: 2px;
  color: var(--muted);
  font-size: 10px;
  text-transform: uppercase;
}

.environment-note {
  display: inline-flex;
  align-items: center;
  color: var(--muted);
  font-size: 12px;
  gap: 7px;
}

.environment-note :deep(svg) {
  color: var(--positive);
}

.environment-separator {
  width: 1px;
  height: 12px;
  background: var(--line-strong);
}

@media (max-width: 640px) {
  .app-header {
    padding: 0 16px;
  }

  .brand-link small,
  .environment-note span:not(:first-of-type) {
    display: none;
  }
}
</style>
