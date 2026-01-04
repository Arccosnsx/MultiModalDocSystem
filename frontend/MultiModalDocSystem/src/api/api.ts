import axios from 'axios';
import type { UploadFile, OCRResult, RAGSegment, ProcessStatus, CleanOCRResponse, OCRDetails } from '../types';

const API_BASE_URL = 'http://localhost:8000';

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 300000, // 增加超时时间，因为OCR处理可能需要较长时间
});

// 文件上传API - 使用FormData
export const uploadFiles = async (files: File[]): Promise<UploadFile[]> => {
    try {
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });

        const response = await apiClient.post('/upload/files', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    } catch (error) {
        console.error('文件上传失败:', error);
        throw error;
    }
};

// 上传单个文件API
export const uploadSingleFile = async (file: File, onProgress?: (progress: number) => void): Promise<UploadFile> => {
    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await apiClient.post('/upload/single', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                    onProgress(progress);
                }
            },
        });

        return response.data;
    } catch (error) {
        console.error('单个文件上传失败:', error);
        throw error;
    }
};

// OCR处理API
export interface OCRProcessRequest {
    file_id: string;
}

export interface OCRProcessResponse extends OCRResult {
    task_id?: string;
}

export const processOCR = async (fileId: string): Promise<OCRProcessResponse> => {
    try {
        const request: OCRProcessRequest = { file_id: fileId };
        const response = await apiClient.post('/process/ocr', request);
        return response.data;
    } catch (error) {
        console.error('OCR处理失败:', error);
        throw error;
    }
};

// 获取OCR处理详细信息API
export const getOCRDetails = async (taskId: string): Promise<OCRDetails> => {
    try {
        const response = await apiClient.get(`/ocr/details/${taskId}`);
        return response.data;
    } catch (error) {
        console.error('获取OCR详情失败:', error);
        throw error;
    }
};

// 单独清洗OCR内容API
export interface CleanOCRRequest {
    ocr_content: string;
    backend?: string;
}

export const cleanOCRContent = async (request: CleanOCRRequest): Promise<CleanOCRResponse> => {
    try {
        const response = await apiClient.post('/process/clean-ocr', request);
        return response.data;
    } catch (error) {
        console.error('OCR清洗失败:', error);
        throw error;
    }
};

// RAG分段处理API
export interface RAGProcessRequest {
    content: string;
    chunk_size?: number;
    overlap?: number;
    llm_backend?: string;
    llm_model?: string;
    llm_timeout?: number;
}

export const processRAG = async (request: RAGProcessRequest): Promise<RAGSegment[]> => {
    try {
        const response = await apiClient.post('/process/rag', request);
        return response.data;
    } catch (error) {
        console.error('RAG处理失败:', error);
        throw error;
    }
};

// 获取处理状态API
export const getProcessStatus = async (taskId: string): Promise<ProcessStatus> => {
    try {
        console.log(`获取任务状态: ${taskId}`);
        const response = await apiClient.get(`/status/${taskId}`);
        console.log('状态响应:', response.data);
        return response.data;
    } catch (error) {
        console.error('获取状态失败:', error);
        throw error;
    }
};

// 确认结果API
export interface ConfirmRequest {
    ocr_result: any;
    rag_segments: any[];
}

export interface ConfirmResponse {
    success: boolean;
    result_path: string;
}

export const confirmResults = async (request: ConfirmRequest): Promise<ConfirmResponse> => {
    try {
        const response = await apiClient.post('/confirm/results', request);
        return response.data;
    } catch (error) {
        console.error('确认结果失败:', error);
        throw error;
    }
};

// 获取文件信息API
export interface FileInfo {
    id: string;
    filename: string;
    size: number;
    filepath: string;
    upload_time: string;
    status: string;
}

export const getFileInfo = async (fileId: string): Promise<FileInfo> => {
    try {
        const response = await apiClient.get(`/file/${fileId}`);
        return response.data;
    } catch (error) {
        console.error('获取文件信息失败:', error);
        throw error;
    }
};

// 工具函数：轮询任务状态
export const pollTaskStatus = async (
    taskId: string,
    interval: number = 1000,
    maxAttempts: number = 300 // 最长5分钟
): Promise<ProcessStatus> => {
    let attempts = 0;

    return new Promise((resolve, reject) => {
        const poll = async () => {
            try {
                attempts++;
                const status = await getProcessStatus(taskId);

                if (status.status === 'completed' || status.status === 'failed') {
                    resolve(status);
                } else if (attempts >= maxAttempts) {
                    reject(new Error('轮询超时'));
                } else {
                    setTimeout(poll, interval);
                }
            } catch (error) {
                reject(error);
            }
        };

        poll();
    });
};

