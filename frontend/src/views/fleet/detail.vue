<template>
  <section class="page" data-module="fleet-detail">
    <header class="page-head">
      <div>
        <h2>车辆档案详情</h2>
        <p class="page-desc">车辆 {{ entry?.['车辆编号'] ?? entryId }} 的登记信息，车辆状态与列表页保持一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="entry">
      <div class="detail-grid">
        <div v-for="field in fields" :key="field" class="detail-item">
          <span class="detail-label">{{ field }}</span>
          <strong class="detail-value">{{ entry[field] ?? '—' }}</strong>
        </div>
      </div>

      <h3 class="section-title">同车牌历史记录（{{ history.length }} 条）</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>车辆编号</th>
            <th>车型类别</th>
            <th>温区数量</th>
            <th>购置日期</th>
            <th>车辆状态</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in history"
            :key="String(item.id)"
            :class="{ current: item.id === entry.id }"
          >
            <td>{{ item['车辆编号'] }}</td>
            <td>{{ item['车型类别'] }}</td>
            <td>{{ item['温区数量'] }}</td>
            <td>{{ item['购置日期'] }}</td>
            <td>{{ item['车辆状态'] }}</td>
          </tr>
          <tr v-if="!history.length">
            <td colspan="5" class="empty-state">该车牌下暂无其他历史记录</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/fleet'
const fields = ["车辆编号", "车牌号码", "车型类别", "制冷机组", "温区数量", "购置日期", "所属车队", "车辆状态"]

const route = useRoute()
const router = useRouter()

const entry = ref<Row | null>(null)
const history = ref<Row[]>([])
const errorMessage = ref('')

const entryId = computed(() => String(route.params.id ?? ''))

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId.value}`)
    if (!response.ok) {
      throw new Error(`冷链车 ${entryId.value} 不存在或已归档`)
    }
    entry.value = (await response.json()) as Row
    await loadHistory()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '车辆档案读取失败'
  }
}

async function loadHistory() {
  const plate = String(entry.value?.['车牌号码'] ?? '')
  if (!plate) return
  try {
    const response = await request(`${ENDPOINT}/history?plate_no=${encodeURIComponent(plate)}`)
    if (!response.ok) return
    const payload = await response.json()
    history.value = payload.items ?? []
  } catch {
    // 历史记录加载失败不影响详情展示
  }
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    void router.push({ name: 'fleet' })
  }
}

onMounted(load)
</script>
