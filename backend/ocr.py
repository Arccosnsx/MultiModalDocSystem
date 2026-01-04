# ocr.py
from pathlib import Path
from typing import Optional, Dict, Any
from paddleocr import PaddleOCRVL
import logging


class OcrEngine:
    def __init__(self, pretty_output: bool = False, show_formula_number: bool = False):
        """
        初始化OCR引擎

        Args:
            pretty_output: 是否美化markdown输出（图表居中）
            show_formula_number: 是否显示公式编号
        """
        self.pretty_output = pretty_output
        self.show_formula_number = show_formula_number

        # 延迟初始化，避免在导入时就加载模型
        self._pipeline = None
        self._logger = logging.getLogger(__name__)

    @property
    def pipeline(self):
        """获取OCR pipeline（延迟加载）"""
        if self._pipeline is None:
            self._logger.info("正在初始化PaddleOCRVL pipeline...")
            self._pipeline = PaddleOCRVL()
            self._logger.info("PaddleOCRVL pipeline初始化完成")
        return self._pipeline

    def extract_markdown(self, file_path: str, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        从文件中提取文本，返回markdown格式

        Args:
            file_path: 输入文件路径（支持图像或PDF）
            save_path: 可选，保存markdown文件的路径

        Returns:
            Dict containing:
                - text: markdown文本
                - images: 提取的图像信息
                - metadata: 处理元数据
        """
        try:
            self._logger.info(f"开始处理文件: {file_path}")

            input_path = Path(file_path)
            if not input_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")

            output = self.pipeline.predict(input=file_path)

            markdown_list = []
            markdown_images = []

            for res in output:
                md_info = res.markdown
                markdown_list.append(md_info)
                markdown_images.append(md_info.get("markdown_images", {}))

            markdown_text = self.pipeline.concatenate_markdown_pages(
                markdown_list
            )

            result = {
                "text": markdown_text,
                "images": markdown_images,
                "metadata": {
                    "input_file": str(input_path),
                    "file_type": input_path.suffix.lower(),
                    "page_count": len(output),
                    "processed_time": self._get_current_time(),
                    "pretty_output": self.pretty_output,
                    "show_formula_number": self.show_formula_number
                }
            }

            if save_path:
                self._save_markdown_file(
                    input_path=input_path,
                    markdown_text=markdown_text,
                    markdown_images=markdown_images,
                    save_path=save_path
                )
                result["saved_path"] = save_path

            self._logger.info(f"文件处理完成: {file_path}, 共{len(output)}页")
            return result

        except Exception as e:
            self._logger.error(f"OCR处理失败: {file_path}, 错误: {str(e)}")
            raise

    def _save_markdown_file(self, input_path: Path, markdown_text: str,
                            markdown_images: list, save_path: str):
        """
        保存markdown文件到指定路径
        """
        save_path_obj = Path(save_path)

        if save_path_obj.is_dir() or save_path.endswith('/'):
            save_path_obj.mkdir(parents=True, exist_ok=True)
            output_file = save_path_obj / f"{input_path.stem}.md"
        else:
            output_file = save_path_obj

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        self._logger.info(f"Markdown保存到: {output_file}")

        for item in markdown_images:
            if item:
                for rel_path, image in item.items():
                    image_path = output_file.parent / rel_path
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(image_path)

        if markdown_images:
            self._logger.info(f"保存了 {len(markdown_images)} 页的图像")

    def _get_current_time(self):
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().isoformat()

    def extract_text(self, file_path: str) -> str:
        """
        提取文本内容（主要接口）

        Args:
            file_path: 输入文件路径

        Returns:
            markdown格式的文本
        """
        result = self.extract_markdown(file_path)
        return result["text"]


_global_ocr_engine = None


def get_ocr_engine(pretty_output: bool = True, show_formula_number: bool = False) -> OcrEngine:
    """
    获取全局OCR引擎实例（确保整个程序周期只实例化一次）
    Args:
        pretty_output: 是否美化markdown输出
        show_formula_number: 是否显示公式编号
    Returns:
        OcrEngine实例
    """
    global _global_ocr_engine
    if _global_ocr_engine is None:
        _global_ocr_engine = OcrEngine(
            pretty_output=pretty_output,
            show_formula_number=show_formula_number
        )
    return _global_ocr_engine
