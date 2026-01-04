<template>
    <div class="confirm-button-container">
        <button @click="handleConfirm" :disabled="disabled" class="confirm-btn" :class="{ 'loading': isLoading }">
            <span v-if="!isLoading">
                <slot>{{ buttonText }}</slot>
            </span>
            <span v-else class="loading-content">
                <span class="loading-spinner"></span>
                处理中...
            </span>
        </button>

        <div v-if="showSuccess" class="success-message">
            <span class="success-icon">✅</span>
            {{ successMessage }}
        </div>

        <div v-if="showError" class="error-message">
            <span class="error-icon">❌</span>
            {{ errorMessage }}
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { confirmResults, type ConfirmRequest, type ConfirmResponse } from '../api/api';

interface Props {
    disabled?: boolean;
    buttonText?: string;
    successMessage?: string;
    errorMessage?: string;
    ocrResult?: any;
    ragSegments?: any[];
}

interface Emits {
    (e: 'confirm'): void;
    (e: 'confirm-success', response: ConfirmResponse): void;
    (e: 'confirm-error', error: any): void;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    buttonText: '确认内容',
    successMessage: '内容已确认并保存成功！',
    errorMessage: '确认失败，请重试',
    ocrResult: () => ({}),
    ragSegments: () => []
});

const emit = defineEmits<Emits>();

const isLoading = ref(false);
const showSuccess = ref(false);
const showError = ref(false);

const handleConfirm = async () => {
    if (props.disabled || isLoading.value) return;

    isLoading.value = true;
    showSuccess.value = false;
    showError.value = false;

    try {
        const request: ConfirmRequest = {
            ocr_result: props.ocrResult,
            rag_segments: props.ragSegments
        };

        emit('confirm');

        const response: ConfirmResponse = await confirmResults(request);
        showSuccess.value = true;

        emit('confirm-success', response);
        setTimeout(() => {
            showSuccess.value = false;
        }, 3000);
    } catch (error) {
        console.error('确认失败:', error);
        showError.value = true;
        emit('confirm-error', error);

        setTimeout(() => {
            showError.value = false;
        }, 3000);
    } finally {
        isLoading.value = false;
    }
};
</script>

<style scoped>
.confirm-button-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
}

.confirm-btn {
    width: 100%;
    max-width: 400px;
    padding: 16px 32px;
    background: linear-gradient(135deg, #409eff, #66b1ff);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 18px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s;
    position: relative;
    overflow: hidden;
}

.confirm-btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.confirm-btn:active:not(:disabled) {
    transform: translateY(0);
}

.confirm-btn:disabled {
    background: linear-gradient(135deg, #c0c4cc, #d3d4d6);
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
}

.confirm-btn.loading {
    cursor: wait;
}

.loading-content {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.loading-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.success-message,
.error-message {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 20px;
    border-radius: 6px;
    font-size: 14px;
    animation: fadeIn 0.3s ease;
}

.success-message {
    background-color: #f6ffed;
    color: #52c41a;
    border: 1px solid #b7eb8f;
}

.error-message {
    background-color: #fff2f0;
    color: #ff4d4f;
    border: 1px solid #ffccc7;
}

.success-icon,
.error-icon {
    font-size: 16px;
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