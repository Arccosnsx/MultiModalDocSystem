<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { OCRResult } from '../types';
import { cleanOCRContent, type CleanOCRRequest, type CleanOCRResponse } from '../api/api';

interface Props {
    result?: OCRResult;
}

interface Emits {
    (e: 'content-update', content: string): void;
    (e: 'clean-start'): void;
    (e: 'clean-success', response: CleanOCRResponse): void;
    (e: 'clean-error', error: any): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const editedContent = ref('');
const isCleaning = ref(false);
const cleanResult = ref<CleanOCRResponse | null>(null);
const showCleanMessage = ref(false);
const cleanMessageType = ref<'success' | 'error' | 'info'>('info');

watch(() => props.result, (newResult) => {
    if (newResult) {
        editedContent.value = newResult.content;
    } else {
        editedContent.value = '';
    }
    cleanResult.value = null;
    showCleanMessage.value = false;
}, { immediate: true });

const handleContentChange = () => {
    emit('content-update', editedContent.value);
};

const resetContent = () => {
    if (props.result) {
        editedContent.value = props.result.content;
        emit('content-update', editedContent.value);
        showCleanMessage.value = false;
    }
};

// 修改清洗函数
const cleanOCRContentHandler = async () => {
    if (!editedContent.value.trim() || isCleaning.value) return;

    isCleaning.value = true;
    showCleanMessage.value = true;
    cleanMessageType.value = 'info';

    try {
        emit('clean-start');

        // 使用后端支持的参数
        const request: CleanOCRRequest = {
            ocr_content: editedContent.value,
            backend: 'deepseek'  // 根据你的后端配置，可以是 'deepseek' 或 'ollama'
        };

        console.log('调用OCR清洗API:', request);

        // 调用OCR清洗API
        const response = await cleanOCRContent(request);
        console.log('OCR清洗响应:', response);

        // 保存清洗结果
        cleanResult.value = response;

        // 更新编辑内容 - 使用后端返回的 cleaned_content
        if (response.cleaned_content) {
            const originalLength = editedContent.value.length;
            const cleanedLength = response.cleaned_content.length;

            editedContent.value = response.cleaned_content;
            emit('content-update', editedContent.value);

            // 计算改善比例（可选）
            if (originalLength > 0) {
                const improvementRatio = (cleanedLength - originalLength) / originalLength;
                cleanResult.value.improvement_ratio = improvementRatio;
            }
        }

        // 显示成功消息
        cleanMessageType.value = 'success';

        // 触发清洗成功事件
        emit('clean-success', response);

    } catch (error: any) {
        console.error('OCR清洗失败:', error);
        cleanMessageType.value = 'error';

        // 显示更详细的错误信息
        const errorMessage = error.response?.data?.detail || error.message || '清洗失败';
        console.error('清洗错误详情:', errorMessage);

        emit('clean-error', error);

    } finally {
        isCleaning.value = false;

        // 3秒后自动隐藏消息
        if (cleanMessageType.value !== 'info') {
            setTimeout(() => {
                showCleanMessage.value = false;
            }, 3000);
        }
    }
};

// 保持原名的别名，避免修改模板
const cleanOCRContent = cleanOCRContentHandler;

const saveContent = () => {
    console.log('保存OCR内容:', editedContent.value);
    // 可以添加保存成功的提示
};

// 计算改善比例文本
const improvementText = computed(() => {
    if (cleanResult.value?.improvement_ratio) {
        const ratio = cleanResult.value.improvement_ratio;
        const percent = (ratio * 100).toFixed(1);
        const direction = ratio > 0 ? '增加' : '减少';
        const absPercent = Math.abs(ratio * 100).toFixed(1);
        return `字符数${direction}了${absPercent}%`;
    }
    return '';
});

// 修改统计数据
const characterCount = computed(() => {
    return editedContent.value.length;
});

const wordCount = computed(() => {
    // 中文字符计数
    const chineseChars = editedContent.value.match(/[\u4e00-\u9fa5]/g) || [];
    // 英文单词计数
    const englishWords = editedContent.value.match(/\b[a-zA-Z]+\b/g) || [];
    return chineseChars.length + englishWords.length;
});

const lineCount = computed(() => {
    return editedContent.value.split('\n').length;
});

const confidenceClass = computed(() => {
    if (!props.result) return '';
    const confidence = props.result.confidence * 100;
    if (confidence > 90) return 'high';
    if (confidence > 70) return 'medium';
    return 'low';
});

// 修改清洗消息文本
const cleanMessageText = computed(() => {
    if (cleanMessageType.value === 'info') {
        return '正在清洗OCR内容...';
    }
    if (cleanMessageType.value === 'success') {
        if (cleanResult.value?.improvement_ratio !== undefined) {
            const ratio = cleanResult.value.improvement_ratio;
            const percent = (ratio * 100).toFixed(1);
            const direction = ratio > 0 ? '增加' : '减少';
            const absPercent = Math.abs(ratio * 100).toFixed(1);
            return `清洗完成！字符数${direction}了${absPercent}%`;
        }
        if (cleanResult.value?.paragraph_count) {
            return `清洗完成！共 ${cleanResult.value.paragraph_count} 个段落`;
        }
        return 'OCR内容清洗完成！';
    }
    if (cleanMessageType.value === 'error') {
        return '清洗失败，请重试';
    }
    return '';
});

const cleanMessageIcon = computed(() => {
    switch (cleanMessageType.value) {
        case 'success': return '✅';
        case 'error': return '❌';
        case 'info': return '🔄';
        default: return '';
    }
});
</script>

<template>
    <div class="ocr-result-editor">
        <div class="editor-header">
            <h3>文字提取结果</h3>
            <div class="file-info" v-if="result">
                <span class="file-name">{{ result.fileName }}</span>
                <span class="confidence" :class="confidenceClass">
                    置信度: {{ (result.confidence * 100).toFixed(1) }}%
                </span>
            </div>
        </div>

        <div class="editor-container">
            <textarea v-model="editedContent" :placeholder="result ? 'OCR识别内容...' : '等待OCR处理结果...'" :disabled="!result"
                class="editor-textarea" rows="15" @input="handleContentChange"></textarea>

            <div class="editor-stats" v-if="result">
                <div class="stat-item">
                    <span class="stat-label">字符数:</span>
                    <span class="stat-value">{{ characterCount }}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">字数:</span>
                    <span class="stat-value">{{ wordCount }}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">行数:</span>
                    <span class="stat-value">{{ lineCount }}</span>
                </div>
                <div v-if="improvementText" class="stat-item improvement">
                    <span class="stat-label">变化:</span>
                    <span class="stat-value">{{ improvementText }}</span>
                </div>
            </div>
        </div>

        <div class="editor-actions" v-if="result">
            <div class="action-group">
                <button @click="resetContent" class="action-btn reset-btn" :disabled="isCleaning">
                    重置修改
                </button>
                <button @click="cleanOCRContent" class="action-btn clean-btn" :disabled="isCleaning">
                    {{ isCleaning ? '清洗中...' : '智能清洗' }}
                </button>
                <button @click="saveContent" class="action-btn save-btn" :disabled="isCleaning">
                    保存修改
                </button>
            </div>

            <!-- 清洗结果信息 -->
            <div v-if="showCleanMessage" class="clean-message" :class="cleanMessageType">
                <span class="clean-icon">{{ cleanMessageIcon }}</span>
                <span class="clean-text">{{ cleanMessageText }}</span>
                <span v-if="cleanResult?.paragraph_count" class="clean-detail">
                    ({{ cleanResult.paragraph_count }}个段落)
                </span>
            </div>
        </div>
    </div>
</template>


<style scoped>
.improvement .stat-value {
    color: #52c41a;
    font-weight: bold;
}

.clean-detail {
    margin-left: 8px;
    font-size: 12px;
    opacity: 0.8;
}

.ocr-result-editor {
    background-color: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    height: 100%;
    display: flex;
    flex-direction: column;
}

.editor-header {
    margin-bottom: 20px;
}

.editor-header h3 {
    margin: 0 0 12px 0;
    color: #333;
}

.file-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background-color: #f5f7fa;
    border-radius: 6px;
}

.file-name {
    font-size: 14px;
    color: #333;
    font-weight: 500;
}

.confidence {
    font-size: 12px;
    padding: 4px 8px;
    border-radius: 12px;
    font-weight: 500;
}

.confidence.high {
    background-color: #f0f9eb;
    color: #67c23a;
}

.confidence.medium {
    background-color: #fdf6ec;
    color: #e6a23c;
}

.confidence.low {
    background-color: #fef0f0;
    color: #f56c6c;
}

.editor-container {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.editor-textarea {
    flex: 1;
    padding: 16px;
    border: 1px solid #dcdfe6;
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.6;
    resize: vertical;
    transition: border-color 0.3s;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.editor-textarea:focus {
    outline: none;
    border-color: #409eff;
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}

.editor-textarea:disabled {
    background-color: #f5f7fa;
    color: #909399;
    cursor: not-allowed;
}

.editor-stats {
    display: flex;
    gap: 16px;
    margin-top: 12px;
    padding: 8px 12px;
    background-color: #f8f9fa;
    border-radius: 6px;
}

.stat-item {
    display: flex;
    align-items: center;
    gap: 6px;
}

.stat-label {
    font-size: 12px;
    color: #666;
}

.stat-value {
    font-size: 14px;
    font-weight: 500;
    color: #333;
}

.editor-actions {
    margin-top: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.action-group {
    display: flex;
    gap: 12px;
}

.action-btn {
    flex: 1;
    padding: 10px 16px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 40px;
}

.action-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.reset-btn {
    background-color: #f5f7fa;
    color: #606266;
    border: 1px solid #dcdfe6;
}

.reset-btn:hover:not(:disabled) {
    background-color: #e4e7ed;
}

.clean-btn {
    background-color: #722ed1;
    color: white;
}

.clean-btn:hover:not(:disabled) {
    background-color: #9254de;
}

.save-btn {
    background-color: #409eff;
    color: white;
}

.save-btn:hover:not(:disabled) {
    background-color: #66b1ff;
}

.clean-message {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-radius: 6px;
    font-size: 14px;
    animation: fadeIn 0.3s ease;
}

.clean-message.success {
    background-color: #f6ffed;
    color: #52c41a;
    border: 1px solid #b7eb8f;
}

.clean-message.error {
    background-color: #fff2f0;
    color: #ff4d4f;
    border: 1px solid #ffccc7;
}

.clean-message.info {
    background-color: #e6f7ff;
    color: #1890ff;
    border: 1px solid #91d5ff;
}

.clean-icon {
    font-size: 16px;
}

.clean-text {
    flex: 1;
}

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>