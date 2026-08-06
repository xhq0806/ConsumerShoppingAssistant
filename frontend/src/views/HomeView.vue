<script setup lang="ts">
import { SafetyCertificateOutlined, ExperimentOutlined } from '@ant-design/icons-vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
</script>

<template>
  <main class="page-shell">
    <a-card class="hero-card" :bordered="false">
      <a-typography-title>购物决策助手</a-typography-title>
      <a-typography-paragraph>
        后端开发基线已进入 {{ appStore.milestone }} 阶段，支持 Fixture 对比草稿、商品解析与
        SKU 确认。业务前端和真实淘宝数据分析尚未开放。
      </a-typography-paragraph>
      <a-space wrap>
        <a-tag color="blue"><ExperimentOutlined /> Fixture Provider</a-tag>
        <a-tag color="green"><SafetyCertificateOutlined /> 合规优先</a-tag>
      </a-space>
    </a-card>
  </main>
</template>
