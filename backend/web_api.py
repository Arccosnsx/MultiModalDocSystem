from segmenter import get_segmenter
import traceback
from ocr import get_ocr_engine
from cleaner import get_cleaner
import os
import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import asyncio
from ocr_processor import OcrProcessor


class UploadFileResponse(BaseModel):
    file_id: str
    filename: str
    upload_time: str
    size: int
    status: str = "uploaded"
    task_id: Optional[str] = None


class OCRRequest(BaseModel):
    file_id: str


class OCRResult(BaseModel):
    file_id: str
    content: str
    processed_time: str
    confidence: Optional[float] = None
    paragraph_count: Optional[int] = None
    task_id: Optional[str] = None


class RAGRequest(BaseModel):
    content: str
    chunk_size: int = 500
    overlap: int = 50
    llm_backend: Optional[str] = "deepseek"
    llm_model: Optional[str] = "qwen2.5:7b"
    llm_timeout: Optional[int] = 300


class RAGSegment(BaseModel):
    id: Optional[int] = None
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    task_id: Optional[int] = None

    class Config:
        extra = "allow"


class ConfirmRequest(BaseModel):
    ocr_result: Dict[str, Any]
    rag_segments: List[Dict[str, Any]]


class ProcessStatus(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str
    created_time: str
    updated_time: str


class FileDatabase:
    def __init__(self, db_file: str = "file_database.json"):
        self.db_file = db_file
        self.db = self._load_database()

    def _load_database(self) -> Dict:
        if os.path.exists(self.db_file):
            with open(self.db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"files": {}, "tasks": {}}

    def save(self):
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(self.db, f, ensure_ascii=False, indent=2)

    def add_file(self, file_id: str, filename: str, size: int, filepath: str):
        file_record = {
            "file_id": file_id,
            "filename": filename,
            "size": size,
            "filepath": filepath,
            "upload_time": datetime.now().isoformat(),
            "status": "uploaded"
        }
        self.db["files"][file_id] = file_record
        self.save()

    def get_file(self, file_id: str) -> Optional[Dict]:
        return self.db["files"].get(file_id)

    def update_file_status(self, file_id: str, status: str):
        if file_id in self.db["files"]:
            self.db["files"][file_id]["status"] = status
            self.save()

    def add_task(self, task_id: str, task_type: str, file_id: Optional[str] = None):
        task_record = {
            "task_id": task_id,
            "type": task_type,
            "file_id": file_id,
            "status": "pending",
            "progress": 0,
            "message": "",
            "created_time": datetime.now().isoformat(),
            "updated_time": datetime.now().isoformat()
        }
        self.db["tasks"][task_id] = task_record
        self.save()

    def update_task(self, task_id: str, status: str = None, progress: int = None, message: str = None):
        if task_id in self.db["tasks"]:
            task = self.db["tasks"][task_id]
            if status is not None:
                task["status"] = status
            if progress is not None:
                task["progress"] = progress
            if message is not None:
                task["message"] = message
            task["updated_time"] = datetime.now().isoformat()
            self.save()

    def get_task(self, task_id: str) -> Optional[Dict]:
        return self.db["tasks"].get(task_id)


class FileStorage:
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _get_date_folder(self) -> str:
        """按日期创建文件夹"""
        today = datetime.now().strftime("%Y%m%d")
        folder_path = os.path.join(self.base_dir, today)
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    def _get_rag_folder(self) -> str:
        """RAG结果保存文件夹"""
        today = datetime.now().strftime("%Y%m%d")
        rag_folder = os.path.join("rag_results", today)
        os.makedirs(rag_folder, exist_ok=True)
        return rag_folder

    def save_uploaded_file(self, file: UploadFile) -> tuple:
        """保存上传的文件"""
        folder_path = self._get_date_folder()
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        filename = f"{file_id}{file_extension}"
        filepath = os.path.join(folder_path, filename)

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        size = os.path.getsize(filepath)

        return file_id, filename, filepath, size

    def save_rag_results(self, file_id: str, ocr_result: Dict, rag_segments: List[Dict]) -> str:
        """保存RAG结果到文件"""
        rag_folder = self._get_rag_folder()
        result_file = os.path.join(rag_folder, f"{file_id}_results.json")

        results = {
            "file_id": file_id,
            "processed_time": datetime.now().isoformat(),
            "ocr_result": ocr_result,
            "rag_segments": rag_segments,
            "segment_count": len(rag_segments)
        }

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        return result_file


app = FastAPI(title="文件处理管道API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


file_db = FileDatabase()
file_storage = FileStorage()


@app.post("/upload/single", response_model=UploadFileResponse)
async def upload_single_file(
    file: UploadFile = File(...)
):
    """上传单个文件"""
    try:

        file_id, filename, filepath, size = file_storage.save_uploaded_file(
            file)

        file_db.add_file(file_id, file.filename, size, filepath)

        task_id = str(uuid.uuid4())
        file_db.add_task(task_id, "file_processing", file_id)
        file_db.update_task(task_id, "uploading", 20, "文件上传成功，准备开始OCR处理")

        return {
            "file_id": file_id,
            "filename": filename,
            "upload_time": datetime.now().isoformat(),
            "size": size,
            "status": "uploaded",
            "task_id": task_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@app.post("/upload/files")
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """批量上传文件"""
    try:
        results = []
        for file in files:
            file_id, filename, filepath, size = file_storage.save_uploaded_file(
                file)
            file_db.add_file(file_id, file.filename, size, filepath)

            task_id = str(uuid.uuid4())
            file_db.add_task(task_id, "file_processing", file_id)
            file_db.update_task(task_id, "uploading", 20, "文件上传成功，准备开始OCR处理")

            results.append({
                "file_id": file_id,
                "filename": filename,
                "upload_time": datetime.now().isoformat(),
                "size": size,
                "status": "uploaded",
                "task_id": task_id
            })

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量上传失败: {str(e)}")


@app.post("/process/ocr")
async def process_ocr(request: OCRRequest):
    """处理OCR或直接解析文件内容"""
    try:

        file_record = file_db.get_file(request.file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")

        file_path = file_record.get("filepath")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件路径不存在")

        task_id = None
        for task_key, task_record in file_db.db["tasks"].items():
            if (task_record.get("file_id") == request.file_id and
                    task_record.get("type") == "file_processing"):
                task_id = task_key
                break

        if not task_id:
            task_id = str(uuid.uuid4())
            file_db.add_task(task_id, "file_processing", request.file_id)

        file_db.update_task(task_id, "processing", 20, "正在解析文件内容...")

        extracted_text, needs_ocr = OcrProcessor.extract_text_from_file(
            file_path)

        file_extension = os.path.splitext(file_path)[1].lower()

        use_ocr = needs_ocr

        if use_ocr:
            file_db.update_task(task_id, "processing_ocr", 40, "使用OCR识别...")

            ocr_engine = get_ocr_engine(
                pretty_output=True,
                show_formula_number=False
            )

            final_text = ocr_engine.extract_text(file_path)
            file_db.update_task(task_id, "processing", 60, "OCR完成，开始数据清洗...")
        else:
            file_db.update_task(task_id, "processing", 40, "文件解析成功，开始数据清洗...")
            final_text = extracted_text
            file_db.update_task(task_id, "processing", 60, "开始数据清洗...")

        cleaner = await get_cleaner(
            backend="deepseek",
            model="deepseek-chat",
            timeout=300
        )

        if not final_text or final_text.strip() == "":
            cleaned_content, cleaned_paragraphs = "", []
        else:

            text_length = len(final_text)
            if text_length <= 5000:

                cleaned_paragraphs = await cleaner.clean(final_text)
                cleaned_content = "\n\n".join(cleaned_paragraphs)
            else:

                file_db.update_task(task_id, "processing",
                                    65, f"文本较长({text_length}字符)，分批处理中...")

                chunks = []
                for i in range(0, text_length, 5000):
                    chunk = final_text[i:i + 5000]
                    chunks.append(chunk)

                all_cleaned_paragraphs = []
                for idx, chunk in enumerate(chunks):
                    file_db.update_task(task_id, "processing",
                                        int(65 + (idx + 1) * 30 / len(chunks)),
                                        f"正在处理第{idx + 1}/{len(chunks)}批文本...")

                    chunk_paragraphs = await cleaner.clean(chunk)
                    all_cleaned_paragraphs.extend(chunk_paragraphs)

                cleaned_paragraphs = all_cleaned_paragraphs
                cleaned_content = "".join(cleaned_paragraphs)

        if use_ocr:
            confidence = 0.95
        elif file_extension in OcrProcessor.TEXT_FILE_EXTENSIONS:
            confidence = 1.0
        elif file_extension == '.docx':
            confidence = 0.99
        elif file_extension == '.pdf':
            confidence = 0.98
        else:
            confidence = 0.95

        file_db.update_file_status(request.file_id, "ocr_processed")

        task_record = file_db.get_task(task_id)
        if task_record:
            task_record["cleaned_content"] = cleaned_content
            task_record["paragraphs"] = cleaned_paragraphs
            task_record["original_ocr_content"] = final_text
            task_record["processing_method"] = "ocr" if use_ocr else "direct_extraction"
            file_db.save()

        file_db.update_task(task_id, "completed", 100, "文件处理完成")

        return OCRResult(
            file_id=request.file_id,
            content=cleaned_content,
            processed_time=datetime.now().isoformat(),
            confidence=confidence,
            paragraph_count=len(cleaned_paragraphs),
            task_id=task_id
        )

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"文件处理发生未预期错误: {error_detail}")

        if 'task_id' in locals():
            file_db.update_task(task_id, "failed", 100, f"系统错误: {str(e)}")


@app.get("/ocr/details/{task_id}")
async def get_ocr_details(task_id: str):
    """获取OCR处理的详细信息"""
    try:
        task_record = file_db.get_task(task_id)
        if not task_record:
            raise HTTPException(status_code=404, detail="任务不存在")

        return {
            "task_id": task_id,
            "status": task_record.get("status"),
            "original_ocr_content": task_record.get("original_ocr_content", ""),
            "cleaned_content": task_record.get("cleaned_content", ""),
            "paragraphs": task_record.get("paragraphs", []),
            "created_time": task_record.get("created_time"),
            "updated_time": task_record.get("updated_time")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


class CleanOCRRequest(BaseModel):
    ocr_content: str
    backend: str = "ollama"


@app.post("/process/clean-ocr")
async def clean_ocr_content(request: CleanOCRRequest):
    """清洗OCR文本"""
    try:

        cleaner = await get_cleaner(
            backend=request.backend,
            model="qwen2.5:7b" if request.backend == "ollama" else "deepseek-chat",
            timeout=300
        )

        cleaned_paragraphs = await cleaner.clean(request.ocr_content)

        return {
            "cleaned_content": "\n\n".join(cleaned_paragraphs),
            "paragraphs": cleaned_paragraphs,
            "paragraph_count": len(cleaned_paragraphs),
            "processed_time": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据清洗失败: {str(e)}")


@app.post("/process/rag", response_model=List[RAGSegment])
async def process_rag(
    request: RAGRequest,
    llm_backend: str = "deepseek",
    llm_model: str = "deepseek-chat",
    llm_timeout: int = 300,
    task_id: Optional[str] = None
):
    """处理RAG分段"""
    try:

        if not task_id:

            task_id = str(uuid.uuid4())
            file_db.add_task(task_id, "rag")

        file_db.update_task(task_id, "processing", 10, "正在初始化RAG分段器...")

        try:

            segmenter = await get_segmenter(
                use_llm_splitting=True,
                llm_backend=llm_backend,
                llm_model=llm_model,
                llm_timeout=llm_timeout
            )

            file_db.update_task(task_id, "processing", 30, "正在执行语义分割...")

            segments_data = await segmenter.segment(
                clean_text=request.content,
                chunk_size=request.chunk_size,
                overlap=request.overlap
            )

            segments = []
            for i, segment_dict in enumerate(segments_data):
                segment = RAGSegment(
                    id=i + 1,
                    content=segment_dict.get("content", ""),
                    metadata=segment_dict.get("metadata", {})
                )
                segments.append(segment)

                progress = min(30 + int((i / len(segments_data)) * 70), 99)
                file_db.update_task(task_id, "processing",
                                    progress, f"已处理 {len(segments)} 个分段")

            file_db.update_task(task_id, "completed", 100,
                                f"RAG处理完成，共生成 {len(segments)} 个分段")

            return segments

        except Exception as seg_error:
            error_msg = f"RAG分段失败: {str(seg_error)}"
            file_db.update_task(task_id, "failed", 100, error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"RAG处理发生未预期错误: {error_detail}")

        if 'task_id' in locals():
            file_db.update_task(task_id, "failed", 100, f"系统错误: {str(e)}")

        raise HTTPException(status_code=500, detail=f"RAG处理失败: {str(e)}")


@app.get("/status/{task_id}")
async def get_status(
    task_id: str
):
    """获取处理状态"""
    try:

        task_record = file_db.get_task(task_id)
        if not task_record:
            print(f"任务 {task_id} 不存在于数据库中")
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        return ProcessStatus(**task_record)
    except HTTPException:
        raise
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"获取状态失败，详细错误: {error_detail}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@app.post("/confirm/results")
async def confirm_results(
    request: ConfirmRequest
):
    """确认并保存结果"""
    try:

        file_id = str(uuid.uuid4())

        result_path = file_storage.save_rag_results(
            file_id=file_id,
            ocr_result=request.ocr_result,
            rag_segments=request.rag_segments
        )

        task_id = str(uuid.uuid4())
        file_db.add_task(task_id, "confirmation")
        file_db.update_task(task_id, "completed", 100,
                            f"结果已保存到: {result_path}")

        return {"success": True, "result_path": result_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"确认结果失败: {str(e)}")


@app.get("/file/{file_id}")
async def get_file_info(
    file_id: str
):
    """获取文件信息"""
    try:
        file_record = file_db.get_file(file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")

        return file_record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件信息失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
