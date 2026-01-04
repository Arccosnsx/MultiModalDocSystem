<template>
    <div class="rag-result-editor">
        <div class="editor-header">
            <h3>RAG分段结果</h3>
            <div class="stats" v-if="segments.length > 0">
                <span class="segment-count">共 {{ segments.length }} 个分段</span>
                <span class="total-chars">{{ totalCharacters }} 字符</span>
                <button @click="processRAGContent" class="process-btn" :disabled="isProcessing || !ragContent">
                    {{ isProcessing ? '处理中...' : '重新处理' }}
                </button>
            </div>
        </div>

        <!-- RAG处理配置 -->
        <div v-if="showConfig && !segments.length" class="rag-config">
            <div class="config-header">
                <h4>RAG处理配置</h4>
                <button @click="toggleConfig" class="config-toggle">
                    {{ showConfig ? '收起' : '展开' }}
                </button>
            </div>
            <div class="config-content">
                <div class="config-item">
                    <label>分段大小</label>
                    <input v-model.number="ragConfig.chunkSize" type="number" min="100" max="2000" step="100" />
                    <span class="config-hint">字符数 (100-2000)</span>
                </div>
                <div class="config-item">
                    <label>重叠大小</label>
                    <input v-model.number="ragConfig.overlap" type="number" min="0" max="500" step="10" />
                    <span class="config-hint">字符数 (0-500)</span>
                </div>
                <div class="config-item">
                    <label>LLM模型</label>
                    <select v-model="ragConfig.llmModel">
                        <option value="deepseek">Deepseek</option>
                        <option value="ollama">Qwen3-7B</option>
                    </select>
                </div>
                <div class="config-item">
                    <label>超时时间</label>
                    <input v-model.number="ragConfig.llmTimeout" type="number" min="30" max="300" step="10" />
                    <span class="config-hint">秒 (30-300)</span>
                </div>
                <button @click="processRAGContent" class="process-btn primary" :disabled="isProcessing || !ragContent">
                    {{ isProcessing ? 'RAG处理中...' : '开始RAG处理' }}
                </button>
            </div>
        </div>

        <!-- 处理状态 -->
        <div v-if="isProcessing" class="processing-status">
            <div class="progress-bar">
                <div class="progress-fill" :style="{ width: `${processingProgress}%` }"></div>
            </div>
            <div class="progress-text">
                {{ processingMessage }}
            </div>
        </div>

        <div class="segments-container" v-if="segments.length > 0">
            <div v-for="segment in editedSegments" :key="segment.id" class="segment-item"
                :class="{ 'editing': editingSegmentId === segment.id }">
                <div class="segment-header">
                    <div class="segment-info">
                        <span class="segment-index">分段 #{{ segment.chunkIndex + 1 }}</span>
                        <span class="segment-meta" v-if="segment.metadata">
                            <template v-if="segment.metadata.page">
                                第 {{ segment.metadata.page }} 页
                            </template>
                            <template v-if="segment.metadata.section">
                                · {{ segment.metadata.section }}
                            </template>
                            <template v-if="segment.metadata.confidence">
                                · 置信度: {{ (segment.metadata.confidence * 100).toFixed(1) }}%
                            </template>
                        </span>
                    </div>
                    <div class="segment-actions">
                        <button @click="editSegment(segment.id)" class="edit-btn"
                            :title="editingSegmentId === segment.id ? '完成编辑' : '编辑内容'">
                            {{ editingSegmentId === segment.id ? '完成' : '编辑' }}
                        </button>
                        <button @click="deleteSegment(segment.id)" class="delete-btn" title="删除分段">
                            删除
                        </button>
                    </div>
                </div>

                <div class="segment-content">
                    <textarea v-if="editingSegmentId === segment.id" v-model="segment.content"
                        @input="updateSegmentContent(segment.id, $event.target.value)" class="segment-textarea" rows="4"
                        autofocus></textarea>
                    <div v-else class="segment-text">
                        {{ segment.content }}
                    </div>
                </div>

                <div class="segment-footer">
                    <span class="char-count">{{ segment.content.length }} 字符</span>
                    <div class="keywords" v-if="segment.metadata?.keywords?.length">
                        <span v-for="keyword in segment.metadata.keywords.slice(0, 5)" :key="keyword"
                            class="keyword-tag">
                            {{ keyword }}
                        </span>
                        <span v-if="segment.metadata.keywords.length > 5" class="more-keywords">
                            +{{ segment.metadata.keywords.length - 5 }}个
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <div class="empty-state" v-else-if="!isProcessing">
            <div class="empty-icon">📝</div>
            <p class="empty-text">{{ ragContent ? '点击开始RAG处理' : '请先提供文本内容进行RAG处理' }}</p>
            <p class="empty-hint">RAG处理将文本智能分割为可用于检索的分段</p>
            <button v-if="ragContent" @click="toggleConfig" class="empty-action-btn">
                配置并开始处理
            </button>
        </div>

        <div class="editor-actions" v-if="segments.length > 0">
            <div class="action-group">
                <button @click="addNewSegment" class="action-btn add-btn">
                    + 添加新分段
                </button>
                <button @click="mergeSegments" class="action-btn merge-btn" :disabled="selectedSegments.length < 2">
                    合并选中 ({{ selectedSegments.length }})
                </button>
                <button @click="saveAllSegments" class="action-btn save-btn">
                    保存所有修改
                </button>
                <button @click="exportSegments" class="action-btn export-btn">
                    导出分段
                </button>
            </div>
        </div>

        <!-- 处理结果信息 -->
        <div v-if="showResultMessage" class="result-message" :class="resultMessageType">
            <span class="result-icon">{{ resultMessageIcon }}</span>
            <span class="result-text">{{ resultMessageText }}</span>
            <button @click="showResultMessage = false" class="close-btn">×</button>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { RAGSegment } from '../types';
import { processRAG, type RAGProcessRequest } from '../api/api';

interface Props {
    segments: RAGSegment[];
    ragContent?: string;  // OCR内容，用于RAG处理
}

interface Emits {
    (e: 'segments-update', segments: RAGSegment[]): void;
    (e: 'rag-start'): void;
    (e: 'rag-success', segments: RAGSegment[]): void;
    (e: 'rag-error', error: any): void;
    (e: 'export-request'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const editedSegments = ref<RAGSegment[]>([]);
const editingSegmentId = ref<string>('');
const selectedSegments = ref<string[]>([]);
const isProcessing = ref(false);
const processingProgress = ref(0);
const processingMessage = ref('');
const showConfig = ref(false);
const showResultMessage = ref(false);
const resultMessageType = ref<'success' | 'error' | 'info'>('info');

// RAG处理配置
const ragConfig = ref({
    chunkSize: 500,
    overlap: 50,
    llmModel: 'deepseek-chat',
    llmBackend: 'deepseek',
    llmTimeout: 60
});

watch(() => props.segments, (newSegments) => {
    editedSegments.value = JSON.parse(JSON.stringify(newSegments));
}, { immediate: true });

watch(() => props.ragContent, (newContent) => {
    if (newContent && !props.segments.length) {
        showConfig.value = true;
    }
}, { immediate: true });

const totalCharacters = computed(() => {
    return editedSegments.value.reduce((total, segment) => total + segment.content.length, 0);
});

const editSegment = (segmentId: string) => {
    if (editingSegmentId.value === segmentId) {
        editingSegmentId.value = '';
        emit('segments-update', editedSegments.value);
    } else {
        editingSegmentId.value = segmentId;
    }
};

const updateSegmentContent = (segmentId: string, content: string) => {
    const segment = editedSegments.value.find(s => s.id === segmentId);
    if (segment) {
        segment.content = content;
    }
};

const deleteSegment = (segmentId: string) => {
    const index = editedSegments.value.findIndex(s => s.id === segmentId);
    if (index !== -1) {
        editedSegments.value.splice(index, 1);
        emit('segments-update', editedSegments.value);
    }
};

const addNewSegment = () => {
    const newSegment: RAGSegment = {
        id: `segment-${Date.now()}`,
        fileId: editedSegments.value[0]?.fileId || '',
        content: '新的分段内容...',
        chunkIndex: editedSegments.value.length,
        metadata: {
            section: '新增分段',
            keywords: [],
            confidence: 0.9
        }
    };
    editedSegments.value.push(newSegment);
    editingSegmentId.value = newSegment.id;
};

const mergeSegments = () => {
    // 实现分段合并逻辑
    console.log('合并分段功能');
    // 这里可以添加选中分段并合并的逻辑
};

const processRAGContent = async () => {
    if (!props.ragContent || isProcessing.value) {
        console.log('无法开始RAG处理:', {
            hasContent: !!props.ragContent,
            isProcessing: isProcessing.value,
            contentLength: props.ragContent?.length
        });
        return;
    }

    console.log('开始RAG处理，内容长度:', props.ragContent.length);

    isProcessing.value = true;
    processingProgress.value = 10;
    processingMessage.value = '准备RAG处理...';
    showResultMessage.value = false;

    try {
        // 触发RAG开始事件
        emit('rag-start');

        processingProgress.value = 30;
        processingMessage.value = '发送请求到服务器...';

        // 使用正确的参数格式
        const request: RAGProcessRequest = {
            content: props.ragContent,
            chunk_size: ragConfig.value.chunkSize,
            overlap: ragConfig.value.overlap,
            llm_model: ragConfig.value.llmModel,
            llm_backend: ragConfig.value.llmBackend,  // 后端需要这个参数
            llm_timeout: ragConfig.value.llmTimeout
        };

        console.log('发送RAG请求:', request);

        processingProgress.value = 50;
        processingMessage.value = '正在处理分段...';

        // 调用RAG处理API
        const segments = await processRAG(request);
        console.log('RAG处理响应:', segments);

        // 格式化分段数据 - 注意后端返回的数据格式
        const formattedSegments: RAGSegment[] = segments.map((seg: any, index) => {
            console.log('处理分段数据:', seg);

            // 根据后端实际返回的数据结构进行调整
            const segmentData = {
                id: seg.id || `rag-${Date.now()}-${index}`,
                fileId: props.segments[0]?.fileId || '',
                content: seg.content || seg.text || '',
                chunkIndex: index,
                metadata: {
                    ...(seg.metadata || {}),
                    confidence: seg.metadata?.confidence || seg.confidence || 0.9
                }
            };
            console.log('格式化后的分段:', segmentData);
            return segmentData;
        });

        // 更新分段数据
        editedSegments.value = formattedSegments;

        processingProgress.value = 100;
        processingMessage.value = 'RAG处理完成！';

        // 显示成功消息
        showResultMessage.value = true;
        resultMessageType.value = 'success';

        // 触发成功事件
        emit('rag-success', formattedSegments);
        emit('segments-update', formattedSegments);

        // 3秒后隐藏处理状态
        setTimeout(() => {
            isProcessing.value = false;
            processingProgress.value = 0;
            processingMessage.value = '';
        }, 2000);

    } catch (error: any) {
        console.error('RAG处理失败:', error);

        // 显示更详细的错误信息
        console.error('错误详情:', {
            message: error.message,
            response: error.response?.data,
            status: error.response?.status
        });

        processingMessage.value = '处理失败';

        // 显示错误消息
        showResultMessage.value = true;
        resultMessageType.value = 'error';

        // 触发错误事件
        emit('rag-error', error);

        // 重置状态
        isProcessing.value = false;
        processingProgress.value = 0;
    }
};

const saveAllSegments = () => {
    emit('segments-update', editedSegments.value);
    console.log('保存所有RAG分段:', editedSegments.value);
};

const exportSegments = () => {
    emit('export-request');
    // 可以添加导出逻辑
};

const toggleConfig = () => {
    showConfig.value = !showConfig.value;
};

const resultMessageText = computed(() => {
    if (resultMessageType.value === 'success') {
        return `RAG处理完成！生成 ${editedSegments.value.length} 个分段`;
    }
    if (resultMessageType.value === 'error') {
        return 'RAG处理失败，请重试';
    }
    return '';
});

const resultMessageIcon = computed(() => {
    switch (resultMessageType.value) {
        case 'success': return '✅';
        case 'error': return '❌';
        case 'info': return 'ℹ️';
        default: return '';
    }
});
</script>

<style scoped>
.rag-result-editor {
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

.stats {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 12px;
    background-color: #f5f7fa;
    border-radius: 6px;
    flex-wrap: wrap;
}

.segment-count,
.total-chars {
    font-size: 14px;
    color: #666;
}

.process-btn {
    padding: 4px 12px;
    background-color: #722ed1;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    transition: background-color 0.3s;
}

.process-btn:hover:not(:disabled) {
    background-color: #9254de;
}

.process-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.process-btn.primary {
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 500;
    border-radius: 6px;
}

.rag-config {
    background-color: #f8f9fa;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 20px;
}

.config-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.config-header h4 {
    margin: 0;
    color: #333;
    font-size: 16px;
}

.config-toggle {
    padding: 4px 8px;
    background: none;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    color: #666;
}

.config-content {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}

@media (max-width: 768px) {
    .config-content {
        grid-template-columns: 1fr;
    }
}

.config-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.config-item label {
    font-size: 12px;
    color: #666;
    font-weight: 500;
}

.config-item input,
.config-item select {
    padding: 6px 10px;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    font-size: 14px;
}

.config-hint {
    font-size: 11px;
    color: #999;
}

.processing-status {
    background-color: #e6f7ff;
    border: 1px solid #91d5ff;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 20px;
}

.progress-bar {
    height: 6px;
    background-color: #e4e7ed;
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 8px;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #409eff, #66b1ff);
    border-radius: 3px;
    transition: width 0.3s ease;
}

.progress-text {
    font-size: 14px;
    color: #1890ff;
    text-align: center;
}

.segments-container {
    flex: 1;
    overflow-y: auto;
    margin-bottom: 20px;
}

.segment-item {
    background-color: #f8f9fa;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    transition: all 0.3s;
}

.segment-item.editing {
    border-color: #409eff;
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}

.segment-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.segment-info {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.segment-index {
    font-weight: 500;
    color: #409eff;
    font-size: 14px;
}

.segment-meta {
    font-size: 12px;
    color: #909399;
}

.segment-actions {
    display: flex;
    gap: 8px;
}

.edit-btn,
.delete-btn {
    padding: 4px 8px;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.3s;
}

.edit-btn {
    background-color: #e6f7ff;
    color: #1890ff;
}

.edit-btn:hover {
    background-color: #bae7ff;
}

.delete-btn {
    background-color: #fff2f0;
    color: #ff4d4f;
}

.delete-btn:hover {
    background-color: #ffccc7;
}

.segment-content {
    margin-bottom: 12px;
}

.segment-textarea {
    width: 100%;
    padding: 12px;
    border: 1px solid #d9d9d9;
    border-radius: 6px;
    font-size: 14px;
    line-height: 1.5;
    resize: vertical;
    font-family: inherit;
}

.segment-textarea:focus {
    outline: none;
    border-color: #409eff;
}

.segment-text {
    font-size: 14px;
    line-height: 1.6;
    color: #333;
}

.segment-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
}

.char-count {
    color: #909399;
}

.keywords {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
}

.keyword-tag {
    padding: 2px 6px;
    background-color: #f0f5ff;
    color: #2d8cf0;
    border-radius: 10px;
    font-size: 11px;
}

.more-keywords {
    color: #999;
    font-size: 11px;
}

.empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #909399;
    padding: 40px 20px;
}

.empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
}

.empty-text {
    font-size: 16px;
    margin: 0 0 8px 0;
    text-align: center;
}

.empty-hint {
    font-size: 14px;
    margin: 0 0 20px 0;
    opacity: 0.8;
    text-align: center;
}

.empty-action-btn {
    padding: 8px 16px;
    background-color: #722ed1;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    transition: background-color 0.3s;
}

.empty-action-btn:hover {
    background-color: #9254de;
}

.editor-actions {
    margin-top: auto;
}

.action-group {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
}

@media (min-width: 768px) {
    .action-group {
        grid-template-columns: repeat(4, 1fr);
    }
}

.action-btn {
    padding: 8px 12px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s;
    text-align: center;
}

.action-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.add-btn {
    background-color: #f6ffed;
    color: #52c41a;
    border: 1px solid #b7eb8f;
}

.add-btn:hover:not(:disabled) {
    background-color: #d9f7be;
}

.merge-btn {
    background-color: #fff7e6;
    color: #fa8c16;
    border: 1px solid #ffd591;
}

.merge-btn:hover:not(:disabled) {
    background-color: #ffe7ba;
}

.save-btn {
    background-color: #409eff;
    color: white;
}

.save-btn:hover:not(:disabled) {
    background-color: #66b1ff;
}

.export-btn {
    background-color: #f0f5ff;
    color: #2d8cf0;
    border: 1px solid #adc6ff;
}

.export-btn:hover:not(:disabled) {
    background-color: #d6e4ff;
}

.result-message {
    position: fixed;
    bottom: 20px;
    right: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    animation: slideIn 0.3s ease;
    max-width: 400px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 1000;
}

.result-message.success {
    background-color: #f6ffed;
    color: #52c41a;
    border: 1px solid #b7eb8f;
}

.result-message.error {
    background-color: #fff2f0;
    color: #ff4d4f;
    border: 1px solid #ffccc7;
}

.result-message.info {
    background-color: #e6f7ff;
    color: #1890ff;
    border: 1px solid #91d5ff;
}

.result-icon {
    font-size: 16px;
}

.result-text {
    flex: 1;
}

.close-btn {
    background: none;
    border: none;
    font-size: 20px;
    color: inherit;
    cursor: pointer;
    padding: 0;
    line-height: 1;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }

    to {
        transform: translateX(0);
        opacity: 1;
    }
}
</style>