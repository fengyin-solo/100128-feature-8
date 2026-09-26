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
        <input v-model.trim="filters.keyword" placeholder="按车辆编号检索" />
      </label>
      <label class="filter-item">
        <span>车牌号码</span>
        <input v-model.trim="filters.plate" placeholder="按车牌号码检索" />
      </label>
      <label class="filter-item">
        <span>所属车队</span>
        <select v-model="filters.fleet">
          <option value="">全部车队</option>
          <option v-for="name in meta.fleets" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>车型类别</span>
        <select v-model="filters.category">
          <option value="">全部车型</option>
          <option v-for="name in meta.categories" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>车辆状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="name in meta.statuses" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>排序方式</span>
        <select v-model="sortField">
          <option v-for="name in meta.sortableFields" :key="name" :value="name">按{{ name }}</option>
        </select>
        <select v-model="sortOrder">
          <option value="asc">升序</option>
          <option value="desc">降序</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in rows" :key="String(row.id)">
          <tr>
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">详情</button>
              <button
                v-if="Number(row['同牌记录数']) > 1"
                class="link"
                type="button"
                @click="toggleHistory(row)"
              >
                {{ expandedRowId === String(row.id) ? '收起历史' : `历史记录(${row['同牌记录数']})` }}
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
          <tr v-if="expandedRowId === String(row.id)" class="history-row">
            <td :colspan="columns.length + 1">
              <div class="history-panel">
                <p class="history-title">
                  车牌 {{ expandedPlate }} 下共 {{ historyRows.length }} 条档案记录，当前行已高亮
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
                    <tr
                      v-for="item in historyRows"
                      :key="String(item.id)"
                      :class="{ 'history-current': String(item.id) === String(row.id) }"
                    >
                      <td>{{ item['车辆编号'] ?? '—' }}</td>
                      <td>{{ item['车型类别'] ?? '—' }}</td>
                      <td>{{ item['温区数量'] ?? '—' }}</td>
                      <td>{{ item['所属车队'] ?? '—' }}</td>
                      <td>{{ item['车辆状态'] ?? '—' }}</td>
                      <td class="row-actions">
                        <button class="link" type="button" @click="openDetail(item)">详情</button>
                        <button class="link" type="button" @click="locateCategory(item)">定位该车型</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </td>
          </tr>
        </template>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyMessage }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条车辆档案记录</span>
      <div class="pagination">
        <button class="btn ghost" type="button" :disabled="page <= 1" @click="gotoPage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button class="btn ghost" type="button" :disabled="page >= totalPages" @click="gotoPage(page + 1)">下一页</button>
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
const PAGE_SIZE = 10
const columns = ["车辆编号", "车牌号码", "车型类别", "制冷机组", "温区数量", "购置日期", "所属车队", "车辆状态"]
const actions = ["调度出车", "维修登记", "申请报废"]
const DEFAULT_SORT = '车辆编号'

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const errorMessage = ref('')
const filters = reactive({ keyword: '', plate: '', fleet: '', category: '', status: '' })
const sortField = ref(DEFAULT_SORT)
const sortOrder = ref<'asc' | 'desc'>('asc')
const meta = reactive({
  fleets: [] as string[],
  categories: [] as string[],
  statuses: [] as string[],
  sortableFields: ['车辆编号', '温区数量', '购置日期'],
})
const stats = ref([{ label: '空闲车辆', value: 0 }, { label: '出车车辆', value: 0 }, { label: '维修车辆', value: 0 }])
const expandedRowId = ref('')
const expandedPlate = ref('')
const historyRows = ref<Row[]>([])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const emptyMessage = computed(() =>
  total.value > 0
    ? '当前页码已超出结果范围，请往前翻页或调整筛选条件'
    : '没有找到符合条件的车辆档案，请调整车辆编号、车牌号码、所属车队或车型类别后重新查询',
)

function first(value: unknown): string {
  if (Array.isArray(value)) return String(value[0] ?? '')
  return value == null ? '' : String(value)
}

/** 把地址栏里的筛选条件读回表单；返回是否有变化，供路由监听决定是否重新取数。 */
function syncFromRoute(): boolean {
  const next = {
    keyword: first(route.query.keyword),
    plate: first(route.query.plate),
    fleet: first(route.query.fleet),
    category: first(route.query.category),
    status: first(route.query.status),
  }
  const nextSort = meta.sortableFields.includes(first(route.query.sort)) ? first(route.query.sort) : DEFAULT_SORT
  const nextOrder = first(route.query.order) === 'desc' ? 'desc' as const : 'asc' as const
  const nextPage = Math.max(1, Number(first(route.query.page)) || 1)
  const changed =
    next.keyword !== filters.keyword ||
    next.plate !== filters.plate ||
    next.fleet !== filters.fleet ||
    next.category !== filters.category ||
    next.status !== filters.status ||
    nextSort !== sortField.value ||
    nextOrder !== sortOrder.value ||
    nextPage !== page.value
  Object.assign(filters, next)
  sortField.value = nextSort
  sortOrder.value = nextOrder
  page.value = nextPage
  return changed
}

/** 当前筛选条件序列化成地址栏参数，进入详情再返回时可以原样恢复。 */
function currentQuery(): Record<string, string> {
  const query: Record<string, string> = {}
  if (filters.keyword) query.keyword = filters.keyword
  if (filters.plate) query.plate = filters.plate
  if (filters.fleet) query.fleet = filters.fleet
  if (filters.category) query.category = filters.category
  if (filters.status) query.status = filters.status
  if (sortField.value !== DEFAULT_SORT) query.sort = sortField.value
  if (sortOrder.value !== 'asc') query.order = sortOrder.value
  if (page.value > 1) query.page = String(page.value)
  return query
}

/** 表单条件变更后提交：保留当前页码，只把条件写回地址栏并重新取数。 */
function commit() {
  collapseHistory()
  void router.replace({ name: 'fleet', query: currentQuery() })
  void loadList()
}

function applyFilters() {
  commit()
}

function resetFilters() {
  Object.assign(filters, { keyword: '', plate: '', fleet: '', category: '', status: '' })
  sortField.value = DEFAULT_SORT
  sortOrder.value = 'asc'
  page.value = 1
  commit()
}

function gotoPage(target: number) {
  if (target < 1 || target > totalPages.value || target === page.value) return
  page.value = target
  commit()
}

function listParams(): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.plate) params.set('plate', filters.plate)
  if (filters.fleet) params.set('fleet', filters.fleet)
  if (filters.category) params.set('category', filters.category)
  if (filters.status) params.set('status', filters.status)
  params.set('sort', sortField.value)
  params.set('order', sortOrder.value)
  return params
}

async function loadList() {
  errorMessage.value = ''
  const params = listParams()
  params.set('page', String(page.value))
  params.set('size', String(PAGE_SIZE))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('冷链车列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '车辆档案列表读取失败'
  }
}

async function loadMeta() {
  try {
    const response = await request(`${ENDPOINT}/meta`)
    if (!response.ok) return
    const payload = await response.json()
    meta.fleets = payload.fleets ?? []
    meta.categories = payload.categories ?? []
    meta.statuses = payload.statuses ?? []
    meta.sortableFields = payload.sortable_fields ?? meta.sortableFields
    const counts = (payload.status_counts ?? {}) as Record<string, number>
    stats.value = [
      { label: '空闲车辆', value: counts['空闲'] ?? 0 },
      { label: '出车车辆', value: counts['出车中'] ?? 0 },
      { label: '维修车辆', value: counts['维修中'] ?? 0 },
    ]
  } catch {
    // 字典数据加载失败不阻塞列表，下拉框退化为只有「全部」
  }
}

function exportRows() {
  window.open(`${ENDPOINT}/export?${listParams().toString()}`, '_blank')
}

function openCreate() {
  errorMessage.value = '冷链车登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  void router.push({ name: 'fleet-detail', params: { id: String(row.id) }, query: currentQuery() })
}

function collapseHistory() {
  expandedRowId.value = ''
  expandedPlate.value = ''
  historyRows.value = []
}

async function fetchHistory(plate: string) {
  const response = await request(`${ENDPOINT}/by-plate/${encodeURIComponent(plate)}`)
  if (!response.ok) {
    throw new Error('同车牌历史记录读取失败')
  }
  const payload = await response.json()
  historyRows.value = payload.items ?? []
}

async function toggleHistory(row: Row) {
  const plate = String(row['车牌号码'] ?? '')
  if (!plate) return
  if (expandedRowId.value === String(row.id)) {
    collapseHistory()
    return
  }
  errorMessage.value = ''
  try {
    await fetchHistory(plate)
    expandedRowId.value = String(row.id)
    expandedPlate.value = plate
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '同车牌历史记录读取失败'
  }
}

/** 从历史记录定位到对应车型：把车型类别设为筛选条件，页码保持不动。 */
function locateCategory(item: Row) {
  filters.category = String(item['车型类别'] ?? '')
  commit()
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('车辆档案动作未生效，请稍后重试')
    }
    const result = await response.json()
    if (!result.ok) {
      throw new Error(result.message || '车辆档案动作未生效，请稍后重试')
    }
    // 状态流转后列表、统计卡片与展开中的历史记录一起刷新，保证口径一致
    const refreshes: Promise<void>[] = [loadList(), loadMeta()]
    if (expandedPlate.value) {
      refreshes.push(fetchHistory(expandedPlate.value))
    }
    await Promise.all(refreshes)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '车辆档案操作失败'
  }
}

// 浏览器前进后退、从详情页带条件返回时，按地址栏参数恢复列表
watch(
  () => route.query,
  () => {
    if (syncFromRoute()) {
      collapseHistory()
      void loadList()
    }
  },
)

onMounted(() => {
  syncFromRoute()
  void loadMeta()
  void loadList()
})
</script>
