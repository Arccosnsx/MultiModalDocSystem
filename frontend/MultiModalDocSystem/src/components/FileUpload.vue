<template>
    <div class="file-upload-container">
        <div class="upload-area" :class="{ 'dragover': isDragging, 'has-files': files.length > 0 }"
            @dragover.prevent="handleDragOver" @dragleave.prevent="handleDragLeave" @drop.prevent="handleDrop"
            @click="triggerFileInput">
            <div class="upload-content">
                <div class="upload-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                        <path d="M14 2H6C4.9 2 4 2.9 4 4V20C4 21.1 4.9 22 6 22H18C19.1 22 20 21.1 20 20V8L14 2Z"
                            stroke="currentColor" stroke-width="2" />
                        <path d="M14 2V8H20" stroke="currentColor" stroke-width="2" />
                        <path d="M12 12V18" stroke="currentColor" stroke-width="2" />
                        <path d="M9 15L12 12L15 15" stroke="currentColor" stroke-width="2" />
                    </svg>
                </div>
                <p class="upload-text">
                    {{ files.length > 0 ? `已选择 ${files.length} 个文件` : '拖拽文件到此处或点击上传' }}
                </p>
                <p class="upload-hint">支持多个文件同时上传</p>
            </div>

            <input ref="fileInput" type="file" multiple @change="handleFileChange" class="file-input"
                accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.txt" />
        </div>

        <div v-if="files.length > 0" class="file-list">
            <div v-for="file in files" :key="file.id" class="file-item">
                <div class="file-info">
                    <span class="file-name">{{ file.name }}</span>
                    <span class="file-size">{{ formatFileSize(file.size) }}</span>
                </div>
                <div class="file-actions">
                    <!-- 显示上传进度 -->
                    <div v-if="file.uploadProgress > 0 && file.uploadProgress < 100" class="upload-progress">
                        {{ file.uploadProgress }}%
                    </div>
                    <button @click="removeFile(file.id)" class="remove-btn"
                        :disabled="file.status === 'uploading'">×</button>
                </div>
                <!-- 状态指示器 -->
                <div v-if="file.status !== 'pending'" class="status-indicator" :class="file.status">
                    <span v-if="file.status === 'uploading'">上传中...</span>
                    <span v-if="file.status === 'success'">✅</span>
                    <span v-if="file.status === 'error'">❌</span>
                </div>
            </div>
        </div>

        <button @click="submitFiles" :disabled="files.length === 0 || isSubmitting" class="submit-btn">
            {{ isSubmitting ? '上传中...' : '提交文件' }}
        </button>
    </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { UploadFile } from '../types';
import { uploadFiles } from '../api/api';

interface Props {
    isSubmitting?: boolean;
    autoUpload?: boolean; // 新增：是否自动上传
}

interface Emits {
    (e: 'file-selected', files: File[]): void;
    (e: 'submit'): void;
    (e: 'upload-success', uploadedFiles: any[]): void; // 新增：上传成功事件
    (e: 'upload-error', error: any): void; // 新增：上传失败事件
}

const props = withDefaults(defineProps<Props>(), {
    isSubmitting: false,
    autoUpload: false,
});

const emit = defineEmits<Emits>();

const fileInput = ref<HTMLInputElement>();
const files = ref<UploadFile[]>([]);
const isDragging = ref(false);
const isSubmittingInternal = ref(false);

const triggerFileInput = () => {
    fileInput.value?.click();
};

const handleFileChange = (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (input.files) {
        handleFiles(Array.from(input.files));
    }
};

const handleDragOver = (event: DragEvent) => {
    event.preventDefault();
    isDragging.value = true;
};

const handleDragLeave = (event: DragEvent) => {
    event.preventDefault();
    isDragging.value = false;
};

const handleDrop = (event: DragEvent) => {
    event.preventDefault();
    isDragging.value = false;

    if (event.dataTransfer?.files) {
        handleFiles(Array.from(event.dataTransfer.files));
    }
};

const handleFiles = (newFiles: File[]) => {
    const uploadFiles: UploadFile[] = newFiles.map(file => ({
        id: generateId(),
        file,
        name: file.name,
        size: file.size,
        type: file.type,
        uploadProgress: 0,
        status: 'pending',
        originalFile: file, // 保存原始文件对象
    }));

    files.value.push(...uploadFiles);
    emit('file-selected', newFiles);

    // 如果启用自动上传，则自动上传文件
    if (props.autoUpload) {
        submitFiles();
    }
};

const removeFile = (fileId: string) => {
    const file = files.value.find(f => f.id === fileId);
    // 如果文件正在上传，不允许删除
    if (file?.status === 'uploading') {
        return;
    }
    files.value = files.value.filter(f => f.id !== fileId);
};

const submitFiles = async () => {
    if (files.value.length === 0 || isSubmittingInternal.value) return;

    isSubmittingInternal.value = true;

    try {
        emit('submit');

        // 获取所有文件的原始File对象
        const fileObjects = files.value.map(f => f.originalFile);

        // 设置所有文件状态为上传中
        files.value.forEach(file => {
            file.status = 'uploading';
            file.uploadProgress = 0;
        });

        // 调用API上传文件 - 使用正确的endpoint
        const uploadedFilesData = await uploadFiles(fileObjects);

        // 更新文件状态 - 映射后端返回的数据格式
        uploadedFilesData.forEach((uploadedFile, index) => {
            if (files.value[index]) {
                const frontendFile = files.value[index];

                // 更新文件信息为后端返回的数据
                frontendFile.id = uploadedFile.file_id;  // 注意：后端返回的是 file_id
                frontendFile.filename = uploadedFile.filename;
                frontendFile.name = uploadedFile.filename; // 兼容现有代码
                frontendFile.size = uploadedFile.size;
                frontendFile.upload_time = uploadedFile.upload_time;
                frontendFile.status = 'success';
                frontendFile.uploadProgress = 100;

                // 保存原始上传响应，供父组件使用
                frontendFile.uploadResponse = uploadedFile;
            }
        });

        // 触发上传成功事件 - 传递后端返回的完整数据
        emit('upload-success', uploadedFilesData);

    } catch (error) {
        console.error('文件上传失败:', error);

        files.value.forEach(file => {
            file.status = 'error';
        });

        emit('upload-error', error);
    } finally {
        isSubmittingInternal.value = false;
    }
};

const clearFiles = () => {
    files.value = [];
    if (fileInput.value) {
        fileInput.value.value = '';
    }
};

const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const generateId = (): string => {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
};

defineExpose({ clearFiles, submitFiles });
</script>

<style scoped>
.file-upload-container {
    width: 100%;
    max-width: 600px;
    margin: 0 auto;
}

.upload-area {
    border: 2px dashed #cccccc;
    border-radius: 12px;
    padding: 48px 24px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s ease;
    background-color: #fafafa;
}

.upload-area:hover {
    border-color: #409eff;
    background-color: #f0f9ff;
}

.upload-area.dragover {
    border-color: #409eff;
    background-color: #e8f4ff;
}

.upload-area.has-files {
    border-style: solid;
}

.upload-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
}

.upload-icon {
    color: #409eff;
    margin-bottom: 8px;
}

.upload-text {
    font-size: 16px;
    font-weight: 500;
    color: #333;
    margin: 0;
}

.upload-hint {
    font-size: 14px;
    color: #666;
    margin: 0;
}

.file-input {
    display: none;
}

.file-list {
    margin-top: 20px;
    max-height: 300px;
    overflow-y: auto;
}

.file-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px;
    background-color: #f5f5f5;
    border-radius: 8px;
    margin-bottom: 8px;
    position: relative;
}

.file-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
}

.file-name {
    font-size: 14px;
    color: #333;
    font-weight: 500;
}

.file-size {
    font-size: 12px;
    color: #666;
}

.file-actions {
    display: flex;
    align-items: center;
    gap: 8px;
}

.upload-progress {
    font-size: 12px;
    color: #409eff;
    font-weight: 500;
}

.remove-btn {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: none;
    background-color: #ff4d4f;
    color: white;
    cursor: pointer;
    font-size: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.3s;
}

.remove-btn:hover:not(:disabled) {
    background-color: #ff7875;
}

.remove-btn:disabled {
    background-color: #c0c4cc;
    cursor: not-allowed;
}

.status-indicator {
    position: absolute;
    right: 40px;
}

.status-indicator.uploading {
    color: #409eff;
}

.status-indicator.success {
    color: #52c41a;
}

.status-indicator.error {
    color: #ff4d4f;
}

.submit-btn {
    width: 100%;
    padding: 14px;
    margin-top: 20px;
    background-color: #409eff;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.3s;
}

.submit-btn:hover:not(:disabled) {
    background-color: #66b1ff;
}

.submit-btn:disabled {
    background-color: #c0c4cc;
    cursor: not-allowed;
}
</style>