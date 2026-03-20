<script setup lang="ts">
import { NiceModal } from '@rpa/components'
import { computed } from 'vue'

import { ProcessModal } from '@/views/Arrange/components/process'
import { WINDOW_NAME } from '@/constants'
import { windowManager } from '@/platform'
import { baseUrl } from '@/utils/env'
import { useFlowStore } from '@/stores/useFlowStore'
import { useProcessStore } from '@/stores/useProcessStore'

import AtomConfig from './AtomConfig.vue'
import {
  getLimitLengthTip,
  useFormItemLimitLength,
  useFormItemRequired,
} from './hooks/useFormItemSort'

const { atomFormItem } = defineProps<{ atomFormItem: RPA.AtomDisplayItem }>()

const flowStore = useFlowStore()
const processStore = useProcessStore()

const isCuaInstructionField = computed(() => {
  return flowStore.activeAtom?.key?.startsWith('ComputerUse.') && atomFormItem.key === 'instruction'
})

const currentInstruction = computed(() => {
  const value = atomFormItem.value
  if (Array.isArray(value)) {
    return value[0]?.value ?? ''
  }

  return typeof value === 'string' ? value : ''
})

async function openCuaDebugModal() {
  if (!flowStore.activeAtom?.id) {
    return
  }

  const state = encodeURIComponent(JSON.stringify({
    atomId: flowStore.activeAtom.id,
    atomSnapshot: flowStore.activeAtom,
    currentLine: flowStore.simpleFlowUIData.findIndex(item => item.id === flowStore.activeAtom?.id) + 1,
    initialInstruction: currentInstruction.value,
    projectId: processStore.project.id,
    processId: processStore.activeProcessId,
    project: processStore.project,
  }))

  windowManager.closeWindow(WINDOW_NAME.CUA_DEBUG)

  await windowManager.createWindow({
    url: `${baseUrl}/cuadebug.html?ts=${Date.now()}&state=${state}`,
    title: 'CUA Debug',
    label: WINDOW_NAME.CUA_DEBUG,
    alwaysOnTop: false,
    position: 'right_center',
    offset: 40,
    width: 360,
    height: 520,
    resizable: false,
    decorations: false,
    fileDropEnabled: false,
    maximizable: false,
    transparent: false,
  }, () => {
    windowManager.showWindow()
  })

  windowManager.hideWindow()
}

// 是否展示 label
const showLabel = computed(() => {
  return atomFormItem.formType?.type !== 'CHECKBOX'
})
</script>

<template>
  <div class="form-container">
    <label
      v-if="showLabel"
      class="form-container-label flex items-center gap-1 text-[rgba(0,0,0,0.45)] dark:text-[rgba(255,255,255,0.45)]"
    >
      <span v-if="atomFormItem.required" class="text-error">*</span>
      <span
        v-if="atomFormItem.title"
        class="text-xs leading-[22px] text-[#000000]/[.65] dark:text-[#FFFFFF]/[.65]"
      >
        {{ atomFormItem.title }}
      </span>
      <span v-if="atomFormItem.subTitle" class="text-[10px] leading-4">
        {{ atomFormItem.subTitle }}
      </span>
      <a-tooltip v-if="atomFormItem.tip" :title="atomFormItem.tip">
        <rpa-hint-icon name="atom-form-tip" width="16px" height="16px" />
      </a-tooltip>
      <span
        v-if="atomFormItem.title === $t('common.selectPythonModule')"
        class="text-xs text-primary ml-auto cursor-pointer"
        @click="NiceModal.show(ProcessModal, { type: 'module' })"
      >
        {{ $t('common.createPythonScript') }}
      </span>
    </label>
    <div v-if="isCuaInstructionField" class="cua-debug-tip">
      <rpa-icon name="info" size="16" class="text-[#eb6e49]" />
      <span class="cua-debug-hint"> AI可能误判，运行将消耗增值服务积分，优先消耗赠送额度。</span>
    </div>
    <div class="form-config-wrap mt-2">
      <AtomConfig :form-item="atomFormItem" />
      <div v-if="isCuaInstructionField" class="cua-debug-trigger-row">
        <span class="cua-debug-hint">用户指令是必填的</span>
        <a-tooltip title="Debug">
          <a-button
            size="small"
            class="cua-debug-trigger"
            @click="openCuaDebugModal"
          >
            <template #icon>
              <rpa-icon name="bottom-pick-menu-create" size="14" />
            </template>
          </a-button>
        </a-tooltip>
      </div>
    </div>
    <article
      v-if="useFormItemRequired(atomFormItem)"
      class="form-container-context-required"
    >
      {{ $t('common.fieldIsRequired', { field: atomFormItem.title }) }}
    </article>
    <article
      v-if="atomFormItem.customizeTip"
      class="form-container-context-required"
    >
      {{ atomFormItem.customizeTip }}
    </article>
    <article
      v-if="!useFormItemLimitLength(atomFormItem)"
      class="form-container-context-required"
    >
      {{ atomFormItem.title }}{{ $t('common.length') }}{{ getLimitLengthTip(atomFormItem.limitLength) || $t('common.exceedLimit') }}
    </article>
  </div>
</template>

<style lang="scss" scoped>
.form-container {
  & + & {
    margin-top: 12px;
  }

  .cua-debug-trigger-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
  }

  .cua-debug-hint {
    flex: 1;
    text-align: left;
    font-size: 12px;
    color: #eb6e49;
  }

  .cua-debug-trigger {
    width: 30px;
    height: 28px;
    padding: 0;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
  }

  .form-container-context-required {
    color: $color-error;
    margin: 4px 0px;
  }
}

:deep(.atom-options_item) {
  margin: 0 !important;
  padding: 4px 0 !important;
}
</style>
