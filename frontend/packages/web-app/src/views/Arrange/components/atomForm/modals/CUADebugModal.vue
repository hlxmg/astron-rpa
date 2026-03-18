<script setup lang="ts">
import { NiceModal } from '@rpa/components'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { fileRead, fileWrite } from '@/api/resource'
import { useFlowStore } from '@/stores/useFlowStore'
import { useProcessStore } from '@/stores/useProcessStore'
import { useRunningStore } from '@/stores/useRunningStore'
import { blob2Text } from '@/utils/common'

const CUA_DEBUG_LOG_PATH = './.cua_debug_runs.jsonl'
const CUA_DEBUG_STREAM_PATH = './.cua_debug_stream.jsonl'

interface CuaDebugEvent {
  event: string
  step?: number
  thought?: string
  screenshot?: string
  status?: string
  message?: string
  instruction?: string
  action_type?: string
  error?: string
}

interface DebugEntry {
  id: string
  kind: 'status' | 'step'
  text: string
  status?: string
  step?: number
  screenshotPath?: string
  screenshotUrl?: string
  timestamp: string
}

const props = defineProps<{
  atomId: string
  initialInstruction: string
}>()

const modal = NiceModal.useModal()
const flowStore = useFlowStore()
const processStore = useProcessStore()
const runningStore = useRunningStore()

const instruction = ref(props.initialInstruction || '')
const collapsed = ref(false)
const loading = ref(false)
const entries = ref<DebugEntry[]>([])
const isSelfRunning = ref(false)
const currentRunId = ref('')
const runStartedAt = ref('')
const finalizedRunId = ref('')
const streamLineCount = ref(0)
const pollTimer = ref<number | null>(null)

const currentAtom = computed(() => flowStore.simpleFlowUIData.find(item => item.id === props.atomId) ?? flowStore.activeAtom)
const currentLine = computed(() => flowStore.simpleFlowUIData.findIndex(item => item.id === props.atomId) + 1)
const instructionItem = computed(() => currentAtom.value?.inputList?.find(item => item.key === 'instruction'))
const isRunning = computed(() => isSelfRunning.value && ['run', 'debug'].includes(runningStore.running))
const runButtonText = computed(() => (isRunning.value ? 'Stop' : 'Run'))
const collapseButtonText = computed(() => (collapsed.value ? 'Expand' : 'Collapse'))
const panelWidth = computed(() => (collapsed.value ? 360 : 460))
const EVENT_MESSAGE_MAP: Record<string, string> = {
  debug_started: 'Debug started',
  waiting_for_valid_action: 'Waiting for a valid action',
  run_finished: 'Run finished',
  max_steps_reached: 'Max steps reached',
  debug_stopped: 'Debug stopped',
  run_failed: 'Run failed',
}


function buildInstructionValue(value: string) {
  const source = instructionItem.value?.value
  if (Array.isArray(source) && source.length > 0) {
    return source.map((item, index) => (index === 0 ? { ...item, value } : item))
  }

  return [{ type: 'str', value }]
}

function syncInstructionToAtom() {
  if (!currentAtom.value) {
    return
  }

  flowStore.setFormItemValue('instruction', buildInstructionValue(instruction.value), currentAtom.value.id)
}


function revokeScreenshotUrls() {
  entries.value.forEach((entry) => {
    if (entry.screenshotUrl) {
      URL.revokeObjectURL(entry.screenshotUrl)
    }
  })
}

function resetRunEntries() {
  revokeScreenshotUrls()
  entries.value = []
  streamLineCount.value = 0
  loading.value = false
  currentRunId.value = ''
  runStartedAt.value = ''
}

async function loadScreenshotUrl(path: string) {
  try {
    const { data } = await fileRead({ path })
    return URL.createObjectURL(data)
  }
  catch (error) {
    console.error('Failed to load screenshot:', error)
    return ''
  }
}

async function hydrateScreenshotUrls() {
  if (collapsed.value) {
    return
  }

  for (const entry of entries.value) {
    if (entry.screenshotPath && !entry.screenshotUrl) {
      entry.screenshotUrl = await loadScreenshotUrl(entry.screenshotPath)
    }
  }
}

function appendEntry(entry: Omit<DebugEntry, 'id' | 'timestamp'> & { timestamp?: string }) {
  entries.value.push({
    id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
    timestamp: entry.timestamp || dayjs().format('YYYY-MM-DD HH:mm:ss'),
    ...entry,
  })
}

function formatEventMessage(event: CuaDebugEvent) {
  if (event.message && EVENT_MESSAGE_MAP[event.message]) {
    return EVENT_MESSAGE_MAP[event.message]
  }

  if (event.error) {
    return event.error
  }

  return event.message || 'Status updated'
}

async function appendEventLog(event: CuaDebugEvent, timestamp: string) {
  loading.value = false

  if (event.event === 'step') {
    appendEntry({
      kind: 'step',
      status: event.status,
      step: event.step,
      text: event.thought || formatEventMessage(event) || 'No thought captured',
      screenshotPath: event.screenshot || '',
      timestamp,
    })

    if (!collapsed.value && event.screenshot) {
      const target = entries.value[entries.value.length - 1]
      target.screenshotUrl = await loadScreenshotUrl(event.screenshot)
    }
    return
  }

  appendEntry({
    kind: 'status',
    status: event.status,
    text: formatEventMessage(event),
    timestamp,
  })
}


async function pollDebugStream() {
  try {
    const { data } = await fileRead({ path: CUA_DEBUG_STREAM_PATH })
    const content = await blob2Text<string>(data)
    const lines = content.split(/\r?\n/).filter(Boolean)
    const nextLines = lines.slice(streamLineCount.value)
    streamLineCount.value = lines.length

    for (const line of nextLines) {
      try {
        const event = JSON.parse(line) as CuaDebugEvent & { timestamp?: string }
        await appendEventLog(event, event.timestamp || dayjs().format('YYYY-MM-DD HH:mm:ss'))
      }
      catch (error) {
        console.error('Failed to parse stream event:', error, line)
      }
    }
  }
  catch {
    // The stream file may not exist before the first step is written.
  }
}

function startPollingDebugStream() {
  stopPollingDebugStream()
  pollTimer.value = window.setInterval(() => {
    void pollDebugStream()
  }, 500)
}

function stopPollingDebugStream() {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function persistCurrentRun(status: string) {
  if (!currentRunId.value) {
    return
  }

  const payload = {
    runId: currentRunId.value,
    projectId: processStore.project.id,
    processId: processStore.activeProcessId,
    atomId: props.atomId,
    atomKey: currentAtom.value?.key || '',
    instruction: instruction.value,
    status,
    startedAt: runStartedAt.value,
    finishedAt: new Date().toISOString(),
    entries: entries.value.map(({ screenshotUrl, ...entry }) => entry),
  }

  try {
    await fileWrite({
      path: CUA_DEBUG_LOG_PATH,
      mode: 'a',
      content: `${JSON.stringify(payload)}
`,
    })
  }
  catch (error) {
    console.error('Failed to persist CUA debug log:', error)
  }
}

async function finalizeRun(status: string) {
  if (!isSelfRunning.value || finalizedRunId.value === currentRunId.value) {
    return
  }

  loading.value = false
  appendEntry({ kind: 'status', text: 'Finished', status })
  stopPollingDebugStream()
  await pollDebugStream()
  await persistCurrentRun(status)
  finalizedRunId.value = currentRunId.value
  isSelfRunning.value = false
}

async function stopCurrentRun(status = 'manual_stop') {
  if (!isSelfRunning.value) {
    return
  }

  await finalizeRun(status)
  if (['run', 'debug'].includes(runningStore.running)) {
    runningStore.stop(processStore.project.id)
  }
}

async function handleRunOrStop() {
  if (isRunning.value) {
    await stopCurrentRun()
    return
  }

  if (runningStore.running !== 'free') {
    message.warning('Another task is running.')
    return
  }

  if (!currentAtom.value || currentLine.value <= 0) {
    message.warning('Current atom is unavailable.')
    return
  }

  syncInstructionToAtom()

  try {
    await processStore.saveProject()
  }
  catch {
    message.error('Failed to save before debug run.')
    return
  }

  resetRunEntries()
  await fileWrite({ path: CUA_DEBUG_STREAM_PATH, mode: 'w', content: '' })
  streamLineCount.value = 0
  loading.value = true
  isSelfRunning.value = true
  currentRunId.value = `${Date.now()}`
  runStartedAt.value = new Date().toISOString()
  finalizedRunId.value = ''

  startPollingDebugStream()

  runningStore.startRun(
    processStore.project.id,
    processStore.activeProcessId,
    currentLine.value,
    currentLine.value,
    { minimizeWindow: false, hideLogWindow: true },
  )
}

async function closePanel(forceStop = false) {
  syncInstructionToAtom()
  if (forceStop) {
    await stopCurrentRun()
  }
  modal.hide()
}

function handleBack() {
  void closePanel(isRunning.value)
}

function handleClose() {
  void closePanel(isRunning.value)
}

function handleAfterOpenChange(open: boolean) {
  if (!open) {
    stopPollingDebugStream()
    modal.resolveHide()
    modal.remove()
  }
}


watch(() => runningStore.running, (newVal, oldVal) => {
  if (oldVal === 'run' && newVal === 'free' && isSelfRunning.value) {
    void finalizeRun(runningStore.status || 'runSuccess')
  }
})

watch(collapsed, (value) => {
  if (!value) {
    void hydrateScreenshotUrls()
  }
})

onBeforeUnmount(() => {
  stopPollingDebugStream()
  revokeScreenshotUrls()
})
</script>

<template>
  <div v-if="modal.visible" class="cua-debug-overlay">
    <div class="cua-debug-panel" :style="{ width: `${panelWidth}px` }">
      <div class="panel-header">
        <div class="panel-header__title">CUA Debug</div>
        <div class="panel-header__actions">
          <a-button size="small" @click="collapsed = !collapsed">
            {{ collapseButtonText }}
          </a-button>
          <a-button size="small" @click="handleClose">
            Close
          </a-button>
        </div>
      </div>

      <div class="cua-debug-modal">
        <section v-if="!collapsed" class="instruction-panel">
          <div class="panel-title">Instruction</div>
          <a-textarea
            v-model:value="instruction"
            :auto-size="{ minRows: 3, maxRows: 6 }"
            placeholder="Enter a CUA instruction"
          />
        </section>

        <section class="log-panel">
          <div class="panel-title">Logs</div>
          <div v-if="loading && entries.length === 0" class="log-loading">
            <a-spin />
            <span>Thinking...</span>
          </div>

          <div v-else-if="entries.length === 0" class="log-empty">
            No debug logs yet
          </div>

          <div v-else class="log-list">
            <div
              v-for="entry in entries"
              :key="entry.id"
              class="log-entry"
              :class="entry.kind === 'step' ? 'log-entry__step' : 'log-entry__status'"
            >
              <div class="log-entry__meta">
                <span>{{ entry.timestamp }}</span>
                <span v-if="entry.step">Step {{ entry.step }}</span>
              </div>
              <div class="log-entry__text">{{ entry.text }}</div>
              <img
                v-if="!collapsed && entry.screenshotUrl"
                :src="entry.screenshotUrl"
                alt="CUA debug screenshot"
                class="log-entry__image"
              >
            </div>
          </div>
        </section>

        <section class="footer-actions">
          <a-button @click="handleBack">
            Back
          </a-button>
          <a-button :danger="isRunning" type="primary" @click="handleRunOrStop">
            {{ runButtonText }}
          </a-button>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.cua-debug-overlay {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 2100;
}

.cua-debug-panel {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.18);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: #f8fafc;
}

.panel-header__title {
  font-size: 14px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
}

.panel-header__actions {
  display: flex;
  gap: 8px;
}

.cua-debug-modal {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.panel-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.72);
}

.log-panel {
  display: flex;
  flex-direction: column;
}


.log-loading,
.log-empty {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(0, 0, 0, 0.45);
  background: #f7f7f9;
  border-radius: 12px;
}

.log-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
}

.log-entry {
  padding: 10px;
  border-radius: 12px;
  background: #f7f7f9;
}

.log-entry__meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.log-entry__text {
  white-space: pre-wrap;
  word-break: break-word;
  color: rgba(0, 0, 0, 0.85);
  font-size: 13px;
  line-height: 1.5;
}

.log-entry__image {
  display: block;
  width: 100%;
  max-height: 180px;
  object-fit: cover;
  margin-top: 10px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.footer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

