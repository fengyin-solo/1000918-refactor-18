<template>
  <section class="page" data-module="contract">
    <header class="page-head">
      <div>
        <h2>委托合同管理</h2>
        <p class="page-desc">维护委托合同，围绕合同编号、委托单位、检测项目、合同金额做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记委托合同</button>
        <button class="btn" type="button" @click="exportRows">导出委托合同清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <button
              v-if="column === '合同编号'"
              class="link"
              type="button"
              @click="openDetail(row)"
            >
              {{ row[column] ?? '—' }}
            </button>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="!rowActions(row).length">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无委托合同数据，可先登记委托合同</td>
        </tr>
      </tbody>
    </table>

    <section v-if="detail" class="detail-panel">
      <header class="detail-head">
        <h3>合同详情</h3>
        <button class="btn ghost" type="button" @click="closeDetail">收起详情</button>
      </header>
      <dl class="detail-grid">
        <template v-for="column in columns" :key="column">
          <dt>{{ column }}</dt>
          <dd>{{ detail[column] ?? '—' }}</dd>
        </template>
      </dl>
      <div class="row-actions">
        <button
          v-for="action in rowActions(detail)"
          :key="action"
          class="link"
          type="button"
          @click="runAction(action, detail)"
        >
          {{ action }}
        </button>
        <span v-if="!rowActions(detail).length" class="detail-empty">当前状态没有可执行动作</span>
      </div>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 条委托合同记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

// 行的业务字段由后端返回；可执行动作也是后端按共享规则算好带下来的，前端不再自己判断
type Row = {
  id: number | string
  可执行动作?: string[]
  [key: string]: unknown
}

type ActionResult = {
  ok: boolean
  message: string
  entry?: Row | null
}

const ENDPOINT = '/api/contract'
const columns = ["合同编号", "委托单位", "检测项目", "合同金额", "签订日期", "约定周期", "联系人", "合同状态"]
const stats = [{"label": "执行中合同", "value": 0}, {"label": "待签订合同", "value": 0}, {"label": "已完成合同", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const detail = ref<Row | null>(null)

const rowActions = (row: Row): string[] => row.可执行动作 ?? []

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '委托合同登记入口尚未接入审批流'
}

function closeDetail() {
  detail.value = null
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('委托合同详情读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '委托合同详情读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = (await response.json().catch(() => null)) as ActionResult | null
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '委托合同动作未生效，请稍后重试')
    }
    await reload()
    if (detail.value && String(detail.value.id) === String(row.id)) {
      detail.value = payload.entry ?? null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '委托合同操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('委托合同列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '委托合同列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.detail-panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-top: 12px; }
.detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail-head h3 { margin: 0; font-size: 15px; }
.detail-grid { display: grid; grid-template-columns: 120px 1fr; gap: 6px 12px; margin: 0 0 10px; font-size: 13px; }
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; }
.detail-empty { color: var(--muted); font-size: 13px; }
</style>
