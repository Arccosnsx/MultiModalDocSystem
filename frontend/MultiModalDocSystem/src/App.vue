<template>
  <div class="app-container">
    <header class="app-header">
      <h1>RAG 文档处理系统</h1>
      <p class="app-subtitle">上传文档 → 文字识别 → RAG分段 → 确认结果</p>
    </header>

    <main class="app-main">
      <div class="upload-section">
        <FileUpload :is-submitting="isUploading" @file-selected="handleFilesSelected"
          @upload-success="handleUploadSuccess" @upload-error="handleUploadError" ref="fileUploadRef" />
      </div>

      <div class="processing-section">
        <ProgressStatus :task-id="currentTaskId" :auto-poll="true" @status-update="handleStatusUpdate"
          @task-completed="handleTaskCompleted" @task-failed="handleTaskFailed" />
      </div>

      <div class="results-section">
        <div class="results-grid">
          <div class="ocr-result">
            <OCRResultEditor :result="ocrResult" @content-update="handleOCRContentUpdate"
              @clean-success="handleOCRCleanSuccess" @clean-error="handleOCRCleanError" />
          </div>
          <div class="rag-result">
            <RAGResultEditor :segments="ragSegments" :rag-content="ocrContentForRAG"
              @segments-update="handleRAGSegmentsUpdate" @rag-success="handleRAGSuccess" @rag-error="handleRAGError"
              ref="ragEditorRef" />
          </div>
        </div>
      </div>

      <div class="confirm-section">
        <ConfirmButton :disabled="!canConfirm" :button-text="confirmButtonText" :ocr-result="ocrResult"
          :rag-segments="ragSegments" @confirm="handleConfirmResults" @confirm-success="handleConfirmSuccess"
          @confirm-error="handleConfirmError" />
      </div>
    </main>

    <footer class="app-footer">
      <p>文档处理系统 © 2025</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue';
import FileUpload from './components/FileUpload.vue';
import ProgressStatus from './components/ProgressStatus.vue';
import OCRResultEditor from './components/OCRResultEditor.vue';
import RAGResultEditor from './components/RAGResultEditor.vue';
import ConfirmButton from './components/ConfirmButton.vue';
import type { UploadFile, OCRResult, RAGSegment } from './types';
import {
  uploadSingleFile,
  processOCR,
  processRAG,
  confirmResults,
  type OCRProcessResponse,
  type ConfirmResponse
} from './api/api';

const fileUploadRef = ref<InstanceType<typeof FileUpload>>();
const ragEditorRef = ref<InstanceType<typeof RAGResultEditor>>();
const selectedFiles = ref<File[]>([]);
const uploadedFiles = ref<UploadFile[]>([]);
const isUploading = ref(false);
const currentTaskId = ref<string>('');
const ocrResult = ref<OCRResult>();
const ragSegments = ref<RAGSegment[]>([]);

// 处理状态
const processingState = ref({
  isProcessingOCR: false,
  isProcessingRAG: false,
  hasOCRError: false,
  hasRAGError: false,
  currentFileId: '' // 添加当前文件ID跟踪
});

const handleFilesSelected = (files: File[]) => {
  selectedFiles.value = files;
  console.log(`已选择 ${files.length} 个文件`);
};

const handleUploadSuccess = async (uploadedFilesData: any[]) => {
  console.log('文件上传成功:', uploadedFilesData);

  // 保存上传的文件数据
  uploadedFiles.value = uploadedFilesData.map(fileData => ({
    id: fileData.file_id,
    filename: fileData.filename,
    originalName: fileData.filename,
    size: fileData.size,
    upload_time: fileData.upload_time,
    status: fileData.status || 'uploaded',
    task_id: fileData.task_id  // 保存任务ID
  }));

  if (uploadedFilesData.length > 0) {
    const firstFile = uploadedFilesData[0];

    // 关键：如果有任务ID，设置给进度组件
    if (firstFile.task_id) {
      currentTaskId.value = firstFile.task_id;
      console.log('设置进度任务ID:', currentTaskId.value);
    }

    // 处理第一个上传的文件
    await processUploadedFile(firstFile);
  }
};

const handleUploadError = (error: any) => {
  console.error('文件上传失败:', error);
  isUploading.value = false;
};

const processUploadedFile = async (uploadedFile: any) => {
  if (!uploadedFile?.file_id) {
    console.error('上传的文件缺少ID:', uploadedFile);
    return;
  }

  try {
    processingState.value.isProcessingOCR = true;
    processingState.value.currentFileId = uploadedFile.file_id;

    console.log('开始OCR处理，文件ID:', uploadedFile.file_id);
    console.log('当前任务ID:', currentTaskId.value);

    // 如果有任务ID，更新后端任务状态
    if (currentTaskId.value) {
      // 这里可以调用后端更新任务状态为OCR处理中
      // 但最简单的是让后端在OCR处理函数中更新任务状态
    }

    const ocrResponse: OCRProcessResponse = await processOCR(uploadedFile.file_id);

    console.log('OCR响应:', ocrResponse);

    // 保存OCR结果
    ocrResult.value = {
      id: ocrResponse.id || `ocr-${Date.now()}`,
      fileId: uploadedFile.file_id,
      fileName: uploadedFile.filename,
      content: ocrResponse.content || '',
      confidence: ocrResponse.confidence || 0.8,
      originalText: ocrResponse.originalText || '',
      processedText: ocrResponse.processedText || '',
      task_id: ocrResponse.task_id || currentTaskId.value  // 使用已有的或新的
    };

    processingState.value.isProcessingOCR = false;


  } catch (error) {
    console.error('OCR处理失败:', error);
    processingState.value.isProcessingOCR = false;
    processingState.value.hasOCRError = true;
  }
};

const processRAGContent = async () => {
  if (!ocrResult.value?.content.trim()) {
    console.error('OCR内容为空，无法进行RAG处理');
    return;
  }

  try {
    processingState.value.isProcessingRAG = true;

    const request = {
      content: ocrResult.value.content,
      chunk_size: 500,
      overlap: 50,
      llm_backend: 'deepseek', // 根据后端修改
      llm_model: 'deepseek-chat', // 根据后端修改
      llm_timeout: 300
    };

    console.log('开始RAG处理');
    const ragData = await processRAG(request);

    // 格式化RAG分段数据
    ragSegments.value = ragData.map((segment, index) => ({
      id: segment.id || `rag-${Date.now()}-${index}`,
      fileId: ocrResult.value?.fileId || '',
      content: segment.content || '',
      chunkIndex: index,
      metadata: segment.metadata || {
        keywords: [],
        section: `分段 ${index + 1}`,
        confidence: 0.9
      }
    }));

    processingState.value.isProcessingRAG = false;
    console.log('RAG处理完成，生成分段数:', ragSegments.value.length);

  } catch (error) {
    console.error('RAG处理失败:', error);
    processingState.value.isProcessingRAG = false;
    processingState.value.hasRAGError = true;
  }
};



const handleOCRContentUpdate = (content: string) => {
  if (ocrResult.value) {
    ocrResult.value.content = content;
  }
};

const handleOCRCleanSuccess = (response: any) => {
  console.log('OCR清洗成功:', response);
  // 可以触发RAG重新处理
  if (ragEditorRef.value) {
    nextTick(() => {
      // 这里可以调用RAG编辑器的重新处理方法
    });
  }
};

const handleOCRCleanError = (error: any) => {
  console.error('OCR清洗失败:', error);
};

const handleRAGSegmentsUpdate = (segments: RAGSegment[]) => {
  ragSegments.value = segments;
};

const handleRAGSuccess = (segments: RAGSegment[]) => {
  ragSegments.value = segments;
  console.log('RAG处理成功，分段数:', segments.length);
};

const handleRAGError = (error: any) => {
  console.error('RAG处理失败:', error);
};

const handleConfirmResults = () => {
  // ConfirmButton组件会处理实际的确认逻辑
  console.log('开始确认结果...');
};

const handleConfirmSuccess = (response: ConfirmResponse) => {
  console.log('结果确认成功:', response);

  if (response.success) {
    // 成功后的操作
    console.log('结果已保存到:', response.result_path);

    // 可以重置状态或显示成功消息
    resetProcessingState();
  }
};

const handleConfirmError = (error: any) => {
  console.error('结果确认失败:', error);
};

const handleStatusUpdate = (status: any) => {
  console.log('状态更新:', {
    status: status.status,
    progress: status.progress,
    message: status.message
  });

  // 可以根据状态更新UI显示
  if (status.status === 'uploading') {
    console.log('文件上传成功，准备OCR处理');
  } else if (status.status === 'processing_ocr') {
    console.log('正在进行OCR处理...');
  } else if (status.status === 'cleaning') {
    console.log('正在清洗数据...');
  } else if (status.status === 'processing_rag') {
    console.log('正在进行RAG分段...');
  }
};

const handleTaskCompleted = (status: any) => {
  console.log('整个处理任务完成:', status);

  if (status.type === 'file_processing' && status.status === 'completed') {
    console.log('文件处理流程全部完成！');
  }
};

const handleTaskFailed = (status: any) => {
  console.error('任务失败:', status);
};

const resetProcessingState = () => {
  // 清除文件
  if (fileUploadRef.value) {
    fileUploadRef.value.clearFiles();
  }

  // 重置状态
  selectedFiles.value = [];
  uploadedFiles.value = [];
  ocrResult.value = undefined;
  ragSegments.value = [];
  currentTaskId.value = '';

  processingState.value = {
    isProcessingOCR: false,
    isProcessingRAG: false,
    hasOCRError: false,
    hasRAGError: false,
    currentFileId: ''
  };
};

// 计算属性
const ocrContentForRAG = computed(() => {
  return ocrResult.value?.content || '';
});

const canConfirm = computed(() => {
  return !!ocrResult.value &&
    ragSegments.value.length > 0 &&
    !processingState.value.isProcessingOCR &&
    !processingState.value.isProcessingRAG;
});

const confirmButtonText = computed(() => {
  if (!canConfirm.value) {
    return '请先完成文件处理';
  }
  return `确认并提交 ${ragSegments.value.length} 个分段`;
});

// 用于FileUpload组件的提交
const handleFileSubmit = () => {
  if (fileUploadRef.value) {
    fileUploadRef.value.submitFiles();
  }
};


</script>

<style scoped>
.app-container {
  min-height: 100vh;
  background-color: #f0f2f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.app-header {
  text-align: center;
  padding: 40px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.app-header h1 {
  margin: 0 0 12px 0;
  font-size: 2.5rem;
  font-weight: 600;
}

.app-subtitle {
  margin: 0;
  font-size: 1.1rem;
  opacity: 0.9;
}

.app-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

.upload-section {
  margin-bottom: 32px;
}

.processing-section {
  margin-bottom: 32px;
}

.results-section {
  margin-bottom: 32px;
}

.results-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  min-height: 600px;
}

@media (max-width: 1024px) {
  .results-grid {
    grid-template-columns: 1fr;
  }
}

.ocr-result,
.rag-result {
  display: flex;
  flex-direction: column;
  min-height: 600px;
}

.confirm-section {
  margin-bottom: 40px;
  display: flex;
  justify-content: center;
}

.app-footer {
  text-align: center;
  padding: 20px;
  color: #666;
  font-size: 14px;
  border-top: 1px solid #e8e8e8;
  background-color: white;
}
</style>