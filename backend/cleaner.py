# data_cleaner.py
import logging
from typing import List, Union
from llm import LLMClient, OllamaClient, DeepSeekClient
from prompt import PromptTemplates


class DataCleaner:

    def __init__(self,
                 backend: str = "ollama",
                 **kwargs):
        """
        初始化数据清洗器
        Args:
            backend: 后端类型，可选 "ollama" 或 "deepseek"
            **kwargs: 传递给后端客户端的参数
        """
        self.backend = backend.lower()
        self.logger = logging.getLogger(__name__)
        self.prompt_templates = PromptTemplates()

        if self.backend == "ollama":
            self.client = OllamaClient(**kwargs)
        elif self.backend == "deepseek":
            self.client = DeepSeekClient(**kwargs)
        else:
            raise ValueError(f"不支持的backend: {backend}")

    async def clean(self, text: str, custom_instruction: str = None) -> List[str]:
        """
        清洗文本并分段
        Args:
            text: OCR返回的markdown文本
            custom_instruction: 自定义清洗指令
        Returns:
            清洗后的分段文本列表
        """
        try:
            self.logger.info(f"开始清洗文本，长度: {len(text)}字符")

            if self.backend == "deepseek":
                prompt = text
            else:
                if custom_instruction:
                    prompt = self.prompt_templates.get_clean_prompt_with_custom_instruction(
                        text, custom_instruction)
                else:
                    prompt = self.prompt_templates.get_clean_prompt(text)

            if self.backend == "deepseek":
                cleaned_text = await self._clean_with_deepseek(text)
            else:
                cleaned_text = await self.client.generate(prompt)

            paragraphs = self._split_into_paragraphs(cleaned_text)

            self.logger.info(f"清洗完成，得到 {len(paragraphs)} 个段落")
            return paragraphs

        except Exception as e:
            self.logger.error(f"文本清洗失败: {str(e)}")
            return self._split_into_paragraphs(text, is_fallback=True)

    async def _clean_with_deepseek(self, text: str) -> str:

        prompt = f"[系统指令]\n请去除以下文段的markdown标记，并合理补充推断因为ocr识别错误的部分，并按照语义进行分段。\n\n[用户输入]\n{text}"
        return await self.client.generate(prompt)

    def _split_into_paragraphs(self, text: str, is_fallback: bool = False) -> List[str]:
        """
        将文本分割成段落
        Args:
            text: 待分割的文本
            is_fallback: 是否为回退模式
        Returns:
            段落列表
        """
        if is_fallback:
            self.logger.warning("使用回退模式分割文本")
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if len(paragraphs) <= 1:
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        return paragraphs

    async def batch_clean(self, texts: List[str], custom_instruction: str = None) -> List[List[str]]:
        """批量清洗文本"""
        if self.backend == "deepseek":
            cleaned_texts = []
            for text in texts:
                try:
                    cleaned_text = await self._clean_with_deepseek(text)
                    cleaned_texts.append(cleaned_text)
                except Exception as e:
                    self.logger.error(f"DeepSeek清洗失败: {str(e)}")
                    cleaned_texts.append(e)
        else:
            prompts = []
            for text in texts:
                if custom_instruction:
                    prompt = self.prompt_templates.get_clean_prompt_with_custom_instruction(
                        text, custom_instruction)
                else:
                    prompt = self.prompt_templates.get_clean_prompt(text)
                prompts.append(prompt)

            cleaned_texts = await self.client.batch_generate(prompts)

        results = []
        for i, cleaned_text in enumerate(cleaned_texts):
            if isinstance(cleaned_text, Exception):
                self.logger.error(f"第 {i} 个文本清洗失败: {str(cleaned_text)}")
                results.append(self._split_into_paragraphs(
                    texts[i], is_fallback=True))
            else:
                results.append(self._split_into_paragraphs(cleaned_text))

        return results

    async def close(self):
        await self.client.close()


_global_cleaner = None


async def get_cleaner(backend: str = "ollama", **kwargs) -> DataCleaner:
    """
    获取全局数据清洗器实例
    Args:
        backend: 后端类型
        **kwargs: 传递给DataCleaner的参数
    Returns:
        DataCleaner实例
    """
    global _global_cleaner
    if _global_cleaner is None:
        _global_cleaner = DataCleaner(backend=backend, **kwargs)
    return _global_cleaner


async def cleanup_cleaner():
    """清理全局清洗器"""
    global _global_cleaner
    if _global_cleaner:
        await _global_cleaner.close()
        _global_cleaner = None
