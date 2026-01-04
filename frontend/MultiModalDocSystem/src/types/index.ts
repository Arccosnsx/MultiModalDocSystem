export interface UploadFile {
    id: string;           // 文件ID（由后端生成）
    filename: string;     // 保存的文件名（带扩展名）
    originalName?: string; // 原始文件名
    size: number;         // 文件大小
    upload_time: string;  // 上传时间
    status: string;       // 状态
    filepath?: string;    // 文件路径
    url?: string;         // 文件URL
}

export interface FileItem {
    id: string;           // 前端生成的临时ID
    file: File;           // 原始File对象
    name: string;
    size: number;
    type: string;
    uploadProgress: number;
    status: string;
}

export interface OCRResult {
    file_id: string;
    content: string;
    processed_time: string;
    confidence?: number;
    paragraph_count?: number;
    task_id?: string;
}

export interface RAGSegment {
    id: number;
    content: string;
    metadata: Record<string, any>;
    embedding?: number[];
}

export interface ProcessStatus {
    task_id: string;
    status: string;
    progress: number;
    message: string;
    created_time: string;
    updated_time: string;
}