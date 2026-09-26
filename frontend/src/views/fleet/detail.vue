<template>
  <section class="page" data-module="fleet">
    <header class="page-head">
      <div>
        <h2>车辆档案详情</h2>
        <p class="page-desc">单台冷链车的完整档案，车辆状态与列表页保持同一口径。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="entry">
      <div class="detail-grid">
        <div v-for="field in columns" :key="field" class="detail-item">
          <span class="detail-label">{{ field }}</span>
          <strong class="detail-value">{{ entry[field] ?? '—' }}</strong>
        </div>
      </div>

      <section v-if="siblings.length" class="history-panel">
        <p class="history-title">
          车牌 {{ entry['车牌号码'] }} 下另有 {{ siblings.length }} 条历史档案记录
        </p>
        <table class="data-table sub-table">
          <thead>
            <tr>
              <th>车辆编号</th>
              <th>车型类别</th>
              <th>温区数量</th>
              <th>所属车队</th>
              <th>车辆状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in siblings" :key="String(item.id)">
              <td>{{ item['车辆编号'] ?? '—' }}</td>
              <td>{{ item['车型类别'] ?? '—' }}</td>
              <td>{{ item['温区数量'] ?? '—' }}</td>
              <td>{{ item['所属车队'] ?? '—' }}</td>
              <td>{{ item['车辆状态'] ?? '—' }}</td>
              <td class="row-actions">
                <button class="link" type="button" @click="openEntry(item)">查看该记录</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/fleet'
const columns = ["车辆编号", "车牌号码", "车型类别", "制冷机组", "温区数量", "购置日期", "所属车队", "车辆状态"]

const route = useRoute()
const router = useRouter()

const entry = ref<Row | null>(null)
const historyRows = ref<Row[]>([])
const errorMessage = ref('')

const siblings = computed(() =>
  historyRows.value.filter((item) => String(item.id) !== String(entry.value?.id ?? '')),
)

async function loadEntry() {
  errorMessage.value = ''
  entry.value = null
  historyRows.value = []
  const entryId = String(route.params.id ?? '')
  try {
    const response = await request(`${ENDPOINT}/${encodeURIComponent(entryId)}`)
    if (response.status === 404) {
      throw new Error(`冷链车 ${entryId} 不存在或已归档`)
    }
    if (!response.ok) {
      throw new Error('冷链车明细读取失败')
    }
    entry.value = (await response.json()) as Row
    await loadHistory()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '冷链车明细读取失败'
  }
}

async function loadHistory() {
  const plate = String(entry.value?.['车牌号码'] ?? '')
  if (!plate) return
  try {
    const response = await request(`${ENDPOINT}/by-plate/${encodeURIComponent(plate)}`)
    if (!response.ok) return
    const payload = await response.json()
    historyRows.value = payload.items ?? []
  } catch {
    // 历史记录加载失败不影响主明细展示
  }
}

/** 跳到同车牌下的另一条档案，地址栏里的列表筛选条件原样带上。 */
function openEntry(item: Row) {
  void router.push({ name: 'fleet-detail', params: { id: String(item.id) }, query: route.query })
}

/** 返回列表：筛选条件与页码通过地址栏参数原样带回。 */
function goBack() {
  void router.push({ name: 'fleet', query: route.query })
}

watch(
  () => route.params.id,
  (next, prev) => {
    if (next && next !== prev) {
      void loadEntry()
    }
  },
)

onMounted(loadEntry)
</script>
