<template>
  <section class="page" data-module="fleet">
    <header class="page-head">
      <div>
        <h2>车辆档案管理</h2>
        <p class="page-desc">维护冷链车，围绕车辆编号、车牌号码、车型类别、制冷机组做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记冷链车</button>
        <button class="btn" type="button" @click="exportRows">导出车辆档案清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>车辆编号</span>
        <input v-model="filters.vehicle_no" placeholder="按车辆编号检索" />
      </label>
      <label class="filter-item">
        <span>车牌号码</span>
        <input v-model="filters.plate_no" placeholder="按车牌号码检索" />
      </label>
      <label class="filter-item">
        <span>所属车队</span>
        <select v-model="filters.fleet_name">
          <option value="">全部车队</option>
          <option v-for="name in fleets" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>车型类别</span>
        <select v-model="filters.category">
          <option value="">全部类别</option>
          <option v-for="name in categories" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>车辆状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="name in statuses" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <p v-if="filters.category" class="sort-hint">
      已限定在车型类别「{{ filters.category }}」内，排序只作用于该类别下的车辆。
    </p>

    <table class="data-table">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column"
            :class="{ sortable: isSortable(column) }"
            @click="isSortable(column) && toggleSort(column)"
          >
            {{ column }}
            <span v-if="isSortable(column) && sortBy === column">{{ sortDir === 'asc' ? '▲' : '▼' }}</span>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in rows" :key="String(row.id)">
          <tr>
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">详情</button>
              <button class="link" type="button" @click="toggleHistory(row)">
                {{ historyOf(row) ? '收起历史' : '历史' }}
              </button>
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="historyOf(row)" class="history-row">
            <td :colspan="columns.length + 1">
              <p class="history-title">
                车牌「{{ row['车牌号码'] }}」共 {{ historyOf(row)?.length }} 条档案记录，当前行为高亮记录
              </p>
              <table class="history-table">
                <thead>
                  <tr>
                    <th>车辆编号</th>
                    <th>车型类别</th>
                    <th>温区数量</th>
                    <th>购置日期</th>
                    <th>车辆状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="item in historyOf(row)"
                    :key="String(item.id)"
                    :class="{ current: item.id === row.id }"
                  >
                    <td>{{ item['车辆编号'] }}</td>
                    <td>{{ item['车型类别'] }}</td>
                    <td>{{ item['温区数量'] }}</td>
                    <td>{{ item['购置日期'] }}</td>
                    <td>{{ item['车辆状态'] }}</td>
                    <td>
                      <button class="link" type="button" @click="locateCategory(String(item['车型类别'] ?? ''))">
                        定位车型
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </template>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            未找到符合条件的车辆档案，可调整上方筛选条件后重新查询（当前筛选条件已保留）
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条车辆档案记录</span>
      <div class="pager">
        <button class="btn" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ maxPage }} 页</span>
        <button class="btn" type="button" :disabled="page >= maxPage" @click="goPage(page + 1)">下一页</button>
        <select v-model.number="size" @change="applyFilters">
          <option :value="10">10 条/页</option>
          <option :value="20">20 条/页</option>
          <option :value="50">50 条/页</option>
        </select>
      </div>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/fleet'
const columns = ["车辆编号", "车牌号码", "车型类别", "制冷机组", "温区数量", "购置日期", "所属车队", "车辆状态"]
const sortableColumns = ["车辆编号", "温区数量", "购置日期"]
const actions = ["调度出车", "维修登记", "申请报废"]
const statuses = ["空闲", "出车中", "维修中", "已报废"]
const PAGE_SIZES = [10, 20, 50]

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const sortBy = ref('车辆编号')
const sortDir = ref<'asc' | 'desc'>('asc')
const filters = reactive({ vehicle_no: '', plate_no: '', fleet_name: '', category: '', status: '' })
const categories = ref<string[]>([])
const fleets = ref<string[]>([])
const stats = ref([{ label: "空闲车辆", value: 0 }, { label: "出车车辆", value: 0 }, { label: "维修车辆", value: 0 }])
const errorMessage = ref('')
const histories = ref<Record<string, Row[]>>({})

const maxPage = computed(() => Math.max(1, Math.ceil(total.value / size.value)))

function isSortable(column: string) {
  return sortableColumns.includes(column)
}

function historyOf(row: Row): Row[] | undefined {
  return histories.value[String(row.id)]
}

function currentQuery(): Record<string, string> {
  const query: Record<string, string> = {}
  if (filters.vehicle_no) query.vehicle_no = filters.vehicle_no
  if (filters.plate_no) query.plate_no = filters.plate_no
  if (filters.fleet_name) query.fleet_name = filters.fleet_name
  if (filters.category) query.category = filters.category
  if (filters.status) query.status = filters.status
  if (sortBy.value !== '车辆编号') query.sort_by = sortBy.value
  if (sortDir.value !== 'asc') query.sort_dir = sortDir.value
  if (page.value > 1) query.page = String(page.value)
  if (size.value !== 10) query.size = String(size.value)
  return query
}

function normalizeQuery(query: Record<string, unknown>): Record<string, string> {
  const entries: Record<string, string> = {}
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    entries[key] = String(value)
  }
  return entries
}

function sameQuery(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  const na = normalizeQuery(a)
  const nb = normalizeQuery(b)
  const keys = new Set([...Object.keys(na), ...Object.keys(nb)])
  return [...keys].every((key) => na[key] === nb[key])
}

function applyQuery() {
  const query = route.query
  filters.vehicle_no = String(query.vehicle_no ?? '')
  filters.plate_no = String(query.plate_no ?? '')
  filters.fleet_name = String(query.fleet_name ?? '')
  filters.category = String(query.category ?? '')
  filters.status = String(query.status ?? '')
  const by = String(query.sort_by ?? '车辆编号')
  sortBy.value = sortableColumns.includes(by) ? by : '车辆编号'
  sortDir.value = String(query.sort_dir) === 'desc' ? 'desc' : 'asc'
  page.value = Math.max(1, Number(query.page) || 1)
  const sizeOption = Number(query.size)
  size.value = PAGE_SIZES.includes(sizeOption) ? sizeOption : 10
}

function syncQuery() {
  const query = currentQuery()
  if (!sameQuery(query, route.query)) {
    void router.replace({ query })
  }
}

function buildParams(withPaging: boolean): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.vehicle_no) params.set('vehicle_no', filters.vehicle_no)
  if (filters.plate_no) params.set('plate_no', filters.plate_no)
  if (filters.fleet_name) params.set('fleet_name', filters.fleet_name)
  if (filters.category) params.set('category', filters.category)
  if (filters.status) params.set('status', filters.status)
  params.set('sort_by', sortBy.value)
  params.set('sort_dir', sortDir.value)
  if (withPaging) {
    params.set('page', String(page.value))
    params.set('size', String(size.value))
  }
  return params
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildParams(true).toString()}`)
    if (!response.ok) {
      throw new Error('冷链车列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 后端会把越界页码收敛到有效范围，这里以返回的页码为准
    page.value = payload.page ?? page.value
    histories.value = {}
    syncQuery()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '车辆档案列表读取失败'
  }
}

// 翻页之后再改条件时保持当前页，由后端把越界页码收敛到最后一页
function applyFilters() {
  void reload()
}

function resetFilters() {
  filters.vehicle_no = ''
  filters.plate_no = ''
  filters.fleet_name = ''
  filters.category = ''
  filters.status = ''
  void reload()
}

function toggleSort(column: string) {
  if (sortBy.value === column) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = column
    sortDir.value = 'asc'
  }
  void reload()
}

function goPage(target: number) {
  if (target < 1 || target > maxPage.value) return
  page.value = target
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export?${buildParams(false).toString()}`, '_blank')
}

function openCreate() {
  errorMessage.value = '冷链车登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  void router.push({ name: 'fleet-detail', params: { id: row.id } })
}

async function toggleHistory(row: Row) {
  const id = String(row.id)
  if (histories.value[id]) {
    const rest = { ...histories.value }
    delete rest[id]
    histories.value = rest
    return
  }
  const plate = String(row['车牌号码'] ?? '')
  try {
    const response = await request(`${ENDPOINT}/history?plate_no=${encodeURIComponent(plate)}`)
    if (!response.ok) {
      throw new Error('同车牌历史记录读取失败')
    }
    const payload = await response.json()
    histories.value = { ...histories.value, [id]: payload.items ?? [] }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '同车牌历史记录读取失败'
  }
}

function locateCategory(category: string) {
  if (!category) return
  filters.category = category
  void reload()
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('车辆档案动作未生效，请稍后重试')
    }
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '车辆档案操作失败'
  }
}

async function loadOptions() {
  try {
    const response = await request(`${ENDPOINT}/options`)
    if (!response.ok) return
    const payload = await response.json()
    categories.value = payload.categories ?? []
    fleets.value = payload.fleets ?? []
  } catch {
    // 筛选项加载失败不阻塞列表
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const payload = await response.json()
    stats.value = [
      { label: '空闲车辆', value: payload['空闲'] ?? 0 },
      { label: '出车车辆', value: payload['出车中'] ?? 0 },
      { label: '维修车辆', value: payload['维修中'] ?? 0 },
    ]
  } catch {
    // 统计卡片加载失败不阻塞列表
  }
}

// 浏览器前进/后退时按地址栏里的条件重新检索；与当前状态一致时不重复请求
watch(
  () => route.query,
  (query) => {
    if (sameQuery(query, currentQuery())) return
    applyQuery()
    void reload()
  },
)

onMounted(() => {
  applyQuery()
  void reload()
  void loadOptions()
  void loadStats()
})
</script>
