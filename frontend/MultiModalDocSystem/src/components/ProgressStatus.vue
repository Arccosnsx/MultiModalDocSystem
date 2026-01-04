<template>
    <div class="progress-status">
        <!-- 头部状态显示 -->
        <div class="status-header">
            <h3>处理进度</h3>
            <div class="status-indicator" :class="currentStatus">
                {{ getStatusText(currentStatus) }}
            </div>
        </div>

        <!-- 进度条 -->
        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" :style="{ width: `${displayProgress}%` }"></div>
            </div>
            <div class="progress-text">
                {{ displayProgress.toFixed(1) }}%
            </div>
        </div>

        <!-- 当前处理信息 -->
        <div class="current-file" v-if="statusInfo?.file_id || currentFile">
            <strong>当前文件:</strong> {{ statusInfo?.file_id || currentFile }}
        </div>

        <div class="status-message">
            <strong>状态:</strong>
            <span v-if="isPolling" class="polling-status">
                <span class="polling-dot">●</span> 实时更新中...
            </span>
            <span v-else-if="errorMessage" class="error-text">
                ❌ {{ errorMessage }}
            </span>
            <span v-else>
                {{ statusInfo?.message || '等待处理任务开始...' }}
            </span>
        </div>

        <!-- 处理步骤 -->
        <div class="steps">
            <div v-for="step in processingSteps" :key="step.id" class="step" :class="{
                'active': step.id === currentStep,
                'completed': isStepCompleted(step.id),
                'failed': currentStatus === 'failed' && step.id === currentStep
            }">
                <div class="step-icon">
                    <span v-if="step.id === 'failed'">❌</span>
                    <span v-else>{{ step.icon }}</span>
                </div>
                <div class="step-label">{{ step.label }}</div>
                <div v-if="step.id === currentStep && elapsedTime" class="step-time">
                    {{ elapsedTime }}
                </div>
            </div>
        </div>

        <!-- 任务信息 -->
        <div v-if="statusInfo?.task_id || taskId" class="task-info">
            <div class="info-item">
                <strong>任务ID:</strong> {{ statusInfo?.task_id || taskId }}
            </div>
            <div v-if="statusInfo?.start_time" class="info-item">
                <strong>开始时间:</strong> {{ formatTime(statusInfo.start_time) }}
            </div>
            <div v-if="statusInfo?.end_time" class="info-item">
                <strong>结束时间:</strong> {{ formatTime(statusInfo.end_time) }}
            </div>
            <div v-if="statusInfo?.error" class="info-item error">
                <strong>错误信息:</strong> {{ statusInfo.error }}
            </div>
            <div v-if="!taskId && !statusInfo" class="info-item">
                <em>等待任务开始...</em>
            </div>
        </div>

        <!-- 操作按钮 -->
        <div v-if="showControls" class="controls">
            <button @click="startPolling" :disabled="isPolling || !taskId" class="control-btn refresh-btn">
                {{ isPolling ? '更新中...' : '刷新状态' }}
            </button>
            <button v-if="isPolling" @click="stopPolling" class="control-btn stop-btn">
                停止轮询
            </button>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue';
import type { ProcessStatus } from '../types';
import { getProcessStatus, pollTaskStatus } from '../api/api';

interface Props {
    taskId?: string;
    autoPoll?: boolean;
    pollInterval?: number;
    showControls?: boolean;
    currentFile?: string; // 添加当前文件属性
}

const props = withDefaults(defineProps<Props>(), {
    taskId: '',
    autoPoll: true,
    pollInterval: 2000,
    showControls: true,
    currentFile: ''
});

interface Emits {
    (e: 'status-update', status: ProcessStatus): void;
    (e: 'polling-start'): void;
    (e: 'polling-stop'): void;
    (e: 'task-completed', status: ProcessStatus): void;
    (e: 'task-failed', status: ProcessStatus): void;
}

const emit = defineEmits<Emits>();

const statusInfo = ref<ProcessStatus | null>(null);
const errorMessage = ref('');
const isPolling = ref(false);
const pollTimer = ref<number | null>(null);
const startTime = ref<number>(0);

// 处理步骤配置
const processingSteps = [
    { id: 'pending', icon: '⏳', label: '等待' },
    { id: 'uploading', icon: '📤', label: '上传' },
    { id: 'processing_ocr', icon: '🔍', label: '文字识别' },
    { id: 'cleaning', icon: '🧹', label: '清洗' },
    { id: 'processing_rag', icon: '📝', label: 'RAG分段' },
    { id: 'completed', icon: '✅', label: '完成' },
    { id: 'failed', icon: '❌', label: '失败' },
];

// 计算当前状态
const currentStatus = computed(() => {
    return statusInfo.value?.status || 'pending';
});

// 计算当前步骤
const currentStep = computed(() => {
    const status = currentStatus.value;

    // 映射状态到步骤
    const statusToStep: Record<string, string> = {
        'pending': 'pending',
        'uploading': 'uploading',
        'processing': 'processing_ocr',
        'processing_ocr': 'processing_ocr',
        'cleaning': 'cleaning',
        'processing_rag': 'processing_rag',
        'completed': 'completed',
        'failed': 'failed'
    };

    return statusToStep[status] || 'pending';
});

// 计算显示进度
const displayProgress = computed(() => {
    if (!statusInfo.value) return 0;

    // 如果有具体进度，使用具体进度值
    if (statusInfo.value.progress !== undefined) {
        return Math.min(statusInfo.value.progress, 100);
    }

    // 根据状态计算进度
    const statusProgress: Record<string, number> = {
        'pending': 0,
        'uploading': 20,
        'processing_ocr': 40,
        'cleaning': 60,
        'processing_rag': 80,
        'completed': 100,
        'failed': 100
    };

    return statusProgress[currentStatus.value] || 0;
});

// 计算已用时间
const elapsedTime = computed(() => {
    if (!startTime.value) return '';

    const elapsed = Date.now() - startTime.value;
    const seconds = Math.floor(elapsed / 1000);

    if (seconds < 60) {
        return `${seconds}秒`;
    } else {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}分${remainingSeconds}秒`;
    }
});

// 获取状态文本
const getStatusText = (status: string): string => {
    const statusMap: Record<string, string> = {
        'pending': '等待中',
        'uploading': '上传中',
        'processing': '处理中',
        'processing_ocr': '文字识别',
        'cleaning': '清洗中',
        'processing_rag': 'RAG分段',
        'completed': '已完成',
        'failed': '已失败'
    };

    return statusMap[status] || status;
};

// 检查步骤是否完成
const isStepCompleted = (stepId: string): boolean => {
    if (currentStatus.value === 'failed') return false;

    const stepIndex = processingSteps.findIndex(step => step.id === stepId);
    const currentIndex = processingSteps.findIndex(step => step.id === currentStep.value);

    return stepIndex < currentIndex && currentStatus.value !== 'failed';
};

const stopPolling = () => {
    isPolling.value = false;
    if (pollTimer.value) {
        clearTimeout(pollTimer.value);
        pollTimer.value = null;
    }
    emit('polling-stop');
};



// 轮询状态
watch(() => props.taskId, (newTaskId) => {
    console.log('任务ID变化:', newTaskId);
    if (newTaskId) {
        initPolling();
    } else {
        stopPolling();
        statusInfo.value = null;
    }
}, { immediate: true });


// 修改轮询函数，添加更多调试信息
const startPolling = async () => {
    if (!props.taskId || isPolling.value) return;

    console.log('开始轮询任务ID:', props.taskId);

    isPolling.value = true;
    errorMessage.value = '';
    startTime.value = Date.now();

    emit('polling-start');

    const poll = async () => {
        try {
            console.log('获取任务状态，任务ID:', props.taskId);
            const status = await getProcessStatus(props.taskId!);
            console.log('获取到的状态:', status);

            statusInfo.value = status;

            // 触发状态更新事件
            emit('status-update', status);

            // 检查任务是否完成
            if (status.status === 'completed') {
                console.log('任务完成:', status);
                stopPolling();
                emit('task-completed', status);
            } else if (status.status === 'failed') {
                console.error('任务失败:', status);
                stopPolling();
                emit('task-failed', status);
            } else if (isPolling.value) {
                // 继续轮询
                pollTimer.value = window.setTimeout(poll, props.pollInterval);
            }
        } catch (error: any) {
            console.error('获取状态失败:', error);
            errorMessage.value = error.message || '获取状态失败';
            stopPolling();
        }
    };

    poll();
};

// 停止轮询


// 初始化轮询
const initPolling = () => {
    if (props.taskId && props.autoPoll) {
        startPolling();
    }
};

// 监听taskId变化
watch(() => props.taskId, (newTaskId) => {
    if (newTaskId) {
        initPolling();
    } else {
        stopPolling();
        statusInfo.value = null;
    }
}, { immediate: true });

// 组件卸载时停止轮询
onUnmounted(() => {
    stopPolling();
});

// 格式化时间
const formatTime = (timestamp: string): string => {
    try {
        return new Date(timestamp).toLocaleString('zh-CN');
    } catch (error) {
        return timestamp;
    }
};
</script>

<style scoped>
.progress-status {
    background-color: #f8f9fa;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.status-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.status-header h3 {
    margin: 0;
    color: #333;
}

.status-indicator {
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
}

.status-indicator.pending {
    background-color: #909399;
    color: white;
}

.status-indicator.uploading {
    background-color: #409eff;
    color: white;
}

.status-indicator.processing,
.status-indicator.processing_ocr {
    background-color: #67c23a;
    color: white;
}

.status-indicator.cleaning {
    background-color: #e6a23c;
    color: white;
}

.status-indicator.processing_rag {
    background-color: #9254de;
    color: white;
}

.status-indicator.completed {
    background-color: #52c41a;
    color: white;
}

.status-indicator.failed {
    background-color: #f56c6c;
    color: white;
}

.progress-container {
    margin-bottom: 20px;
}

.progress-bar {
    height: 8px;
    background-color: #e4e7ed;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 8px;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #409eff, #66b1ff);
    border-radius: 4px;
    transition: width 0.5s ease;
}

.progress-text {
    text-align: right;
    font-size: 14px;
    color: #666;
}

.current-file,
.status-message {
    margin-bottom: 12px;
    padding: 8px 12px;
    background-color: white;
    border-radius: 6px;
    font-size: 14px;
}

.current-file strong,
.status-message strong {
    color: #333;
    margin-right: 8px;
}

.polling-status {
    color: #409eff;
    font-weight: 500;
}

.polling-dot {
    display: inline-block;
    animation: blink 1.5s infinite;
    color: #409eff;
}

@keyframes blink {

    0%,
    50% {
        opacity: 1;
    }

    51%,
    100% {
        opacity: 0.3;
    }
}

.error-text {
    color: #f56c6c;
    font-weight: 500;
}

.steps {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 8px;
    margin-top: 24px;
    margin-bottom: 20px;
}

@media (max-width: 1200px) {
    .steps {
        grid-template-columns: repeat(4, 1fr);
    }
}

@media (max-width: 768px) {
    .steps {
        grid-template-columns: repeat(2, 1fr);
    }
}

.step {
    text-align: center;
    opacity: 0.6;
    transition: all 0.3s;
    padding: 8px;
    border-radius: 8px;
    background-color: white;
    position: relative;
}

.step.active {
    opacity: 1;
    transform: scale(1.05);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    border: 1px solid #409eff;
}

.step.completed {
    opacity: 1;
    background-color: #f6ffed;
}

.step.failed {
    opacity: 1;
    background-color: #fff2f0;
    border-color: #f56c6c;
}

.step-icon {
    font-size: 20px;
    margin-bottom: 4px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.step-label {
    font-size: 11px;
    color: #666;
    margin-bottom: 4px;
    height: 16px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.step.active .step-label {
    color: #409eff;
    font-weight: 500;
}

.step.completed .step-label {
    color: #52c41a;
}

.step.failed .step-label {
    color: #f56c6c;
}

.step-time {
    font-size: 10px;
    color: #999;
    height: 12px;
}

.task-info {
    background-color: white;
    border-radius: 8px;
    padding: 12px;
    margin-top: 16px;
    border: 1px solid #e4e7ed;
}

.info-item {
    font-size: 12px;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
}

.info-item strong {
    color: #666;
    margin-right: 8px;
}

.info-item.error {
    color: #f56c6c;
    background-color: #fff2f0;
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid #ffccc7;
}

.controls {
    display: flex;
    gap: 8px;
    margin-top: 16px;
}

.control-btn {
    flex: 1;
    padding: 8px 12px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s;
}

.control-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.refresh-btn {
    background-color: #409eff;
    color: white;
}

.refresh-btn:hover:not(:disabled) {
    background-color: #66b1ff;
}

.stop-btn {
    background-color: #f56c6c;
    color: white;
}

.stop-btn:hover:not(:disabled) {
    background-color: #ff7875;
}
</style>