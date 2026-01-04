import json
import re
import tiktoken
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import logging

from llm import LLMClient, OllamaClient, DeepSeekClient


class Chunk:
    """文本块类"""

    def __init__(self,
                 content: str,
                 chunk_id: int,
                 metadata: Optional[Dict[str, Any]] = None):
        self.content = content
        self.chunk_id = chunk_id
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata
        }

    def __repr__(self):
        return f"Chunk(id={self.chunk_id}, len={len(self.content)}, metadata={self.metadata})"


class TokenCounter:
    """Token计数器"""

    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        初始化Token计数器

        Args:
            encoding_name: 编码名称，支持：
                - "cl100k_base" (GPT-3.5/4)
                - "p50k_base"
                - "r50k_base"
        """
        try:
            self.encoder = tiktoken.get_encoding(encoding_name)
        except:
            self.encoder = None
            self.fallback = True
        else:
            self.fallback = False

    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        if self.fallback or self.encoder is None:
            return len(text) // 2
        return len(self.encoder.encode(text))

    def split_by_tokens(self, text: str, max_tokens: int) -> List[str]:
        """按最大token数分割文本"""
        if self.fallback or self.encoder is None:
            return self._split_by_chars(text, max_tokens * 4)

        tokens = self.encoder.encode(text)
        chunks = []

        for i in range(0, len(tokens), max_tokens):
            chunk_tokens = tokens[i:i + max_tokens]
            chunk_text = self.encoder.decode(chunk_tokens)
            chunks.append(chunk_text)

        return chunks

    def _split_by_chars(self, text: str, max_chars: int) -> List[str]:
        """按字符数分割文本"""
        chunks = []
        for i in range(0, len(text), max_chars):
            chunks.append(text[i:i + max_chars])
        return chunks


class RAGSplitter(ABC):
    """RAG分割器抽象基类"""

    @abstractmethod
    async def split_by_semantics(self,
                                 text: str,
                                 chunk_size: int = 500,
                                 overlap: int = 50) -> List[Chunk]:
        """按语义分割文本"""
        pass


class LLMRAGSplitter(RAGSplitter):
    """基于LLM的RAG分割器"""

    def __init__(self,
                 llm_backend: str = "deepseek",
                 llm_model: str = "qwen2.5:7b",
                 llm_timeout: int = 300,
                 max_context_size: int = 4000):
        """
        初始化LLM分割器

        Args:
            llm_backend: LLM后端类型，"ollama" 或 "deepseek"
            llm_model: 使用的模型名称
            llm_timeout: 请求超时时间
            max_context_size: 最大上下文长度（token）
        """
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        self.llm_timeout = llm_timeout
        self.max_context_size = max_context_size
        self.llm_client = self._create_llm_client()
        self.token_counter = TokenCounter()
        self.logger = logging.getLogger(__name__)

    def _create_llm_client(self) -> LLMClient:
        """创建LLM客户端"""
        if self.llm_backend == "ollama":
            return OllamaClient(
                base_url="http://localhost:11434",
                model=self.llm_model,
                timeout=self.llm_timeout
            )
        elif self.llm_backend == "deepseek":
            return DeepSeekClient(
                model=self.llm_model,
                timeout=self.llm_timeout
            )
        else:
            raise ValueError(f"不支持的LLM后端: {self.llm_backend}")

    async def split_by_semantics(self,
                                 text: str,
                                 chunk_size: int = 500,
                                 overlap: int = 50) -> List[Chunk]:
        """
        按语义分割文本

        Args:
            text: 清洗后的文本
            chunk_size: 每个chunk的最大token数
            overlap: chunk之间的重叠token数

        Returns:
            分割后的Chunk列表
        """
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            return []

        self.logger.info(
            f"开始RAG分割，共{len(paragraphs)}个段落，目标chunk_size={chunk_size}")

        chunks = []
        chunk_id = 0
        window_size = 4
        i = 0

        while i < len(paragraphs):
            window_paragraphs = paragraphs[i:min(
                i + window_size, len(paragraphs))]

            window_text = "".join(window_paragraphs)
            window_tokens = self.token_counter.count_tokens(window_text)

            if window_tokens <= chunk_size:
                chunk = self._create_chunk(
                    chunk_id=chunk_id,
                    content=window_text,
                    start_para=i,
                    end_para=min(i + window_size, len(paragraphs)) - 1,
                    chunk_size=chunk_size,
                    overlap=overlap
                )
                chunks.append(chunk)
                chunk_id += 1
                i += window_size
            else:
                sub_chunks = await self._split_window(
                    window_text=window_text,
                    window_start=i,
                    chunk_id_start=chunk_id,
                    chunk_size=chunk_size,
                    overlap=overlap
                )

                chunks.extend(sub_chunks)
                chunk_id += len(sub_chunks)
                i += window_size

        self.logger.info(f"RAG分割完成，共生成{len(chunks)}个chunks")
        return chunks

    async def _split_window(self,
                            window_text: str,
                            window_start: int,
                            chunk_id_start: int,
                            chunk_size: int,
                            overlap: int) -> List[Chunk]:
        """分割窗口文本"""
        try:
            prompt = f"""你要执行的是Rag分段操作，请将以下文档按语义完整性分块。
            要求：
            1. 保持语义完整性，不要在句子中间分割
            2. 输出JSON格式
            3. 每块内容应该是连贯的段落
            4. 每块≤{chunk_size} token，并且与前一块有 {overlap} token 的重复
            文档内容：
            {window_text}
            EXAMPLE JSON OUTPUT:
            {{
            'content': ["段落1", "段落2", ...]
            }}
            """
            response = await self.llm_client.generate(prompt, is_json=True)

            print(f"LLM响应: {response}")

            try:
                json_match = re.search(
                    r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1)

                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    response = json_match.group(0)

                result = json.loads(response)

                if isinstance(result, dict):
                    content_data = result.get("content", [])
                    if isinstance(content_data, list):
                        chunks_data = []
                        for content_item in content_data:
                            if isinstance(content_item, str):
                                chunks_data.append({"content": content_item})
                            elif isinstance(content_item, dict):
                                chunks_data.append(content_item)
                            else:
                                chunks_data.append(
                                    {"content": str(content_item)})
                    else:
                        chunks_data = [{"content": str(content_data)}]
                elif isinstance(result, list):
                    chunks_data = result
                else:
                    chunks_data = [{"content": str(result)}]

                if not isinstance(chunks_data, list):
                    raise ValueError("返回结果不是列表")

            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"LLM返回不是有效JSON，使用备用分割: {str(e)}")
                chunks_data = self._fallback_split(window_text, chunk_size)

            chunks = []
            for idx, chunk_data in enumerate(chunks_data):
                if isinstance(chunk_data, dict):
                    content = chunk_data.get("content", "")
                    if not isinstance(content, str):
                        content = str(content)
                else:
                    content = str(chunk_data)

                if content and content.strip():
                    chunk = self._create_chunk(
                        chunk_id=chunk_id_start + idx,
                        content=content.strip(),
                        start_para=window_start,
                        end_para=window_start,
                        chunk_size=chunk_size,
                        overlap=overlap
                    )
                    chunks.append(chunk)
                else:
                    self.logger.warning(f"跳过空内容块: {chunk_data}")

            return chunks

        except Exception as e:
            self.logger.error(f"窗口分割失败，使用备用方案: {str(e)}")
            return self._fallback_split_to_chunks(
                window_text,
                window_start,
                chunk_id_start,
                chunk_size,
                overlap
            )

    def _fallback_split(self, text: str, chunk_size: int) -> List[Dict[str, str]]:
        chunks_text = self.token_counter.split_by_tokens(text, chunk_size)
        return [{"content": chunk} for chunk in chunks_text]

    def _fallback_split_to_chunks(self,
                                  text: str,
                                  window_start: int,
                                  chunk_id_start: int,
                                  chunk_size: int,
                                  overlap: int) -> List[Chunk]:
        chunks_text = self.token_counter.split_by_tokens(text, chunk_size)
        chunks = []

        for idx, chunk_text in enumerate(chunks_text):
            chunk = self._create_chunk(
                chunk_id=chunk_id_start + idx,
                content=chunk_text,
                start_para=window_start,
                end_para=window_start,
                chunk_size=chunk_size,
                overlap=overlap,
                is_fallback=True
            )
            chunks.append(chunk)

        return chunks

    def _create_chunk(self,
                      chunk_id: int,
                      content: str,
                      start_para: int,
                      end_para: int,
                      chunk_size: int,
                      overlap: int,
                      is_fallback: bool = False) -> Chunk:
        metadata = {
            "chunk_size": chunk_size,
            "overlap": overlap,
            "start_paragraph": start_para,
            "end_paragraph": end_para,
            "token_count": self.token_counter.count_tokens(content),
            "char_count": len(content),
            "is_fallback": is_fallback,
            "split_method": "llm_semantic" if not is_fallback else "token_based",
            "llm_backend": self.llm_backend,
            "llm_model": self.llm_model
        }

        return Chunk(
            content=content.strip(),
            chunk_id=chunk_id,
            metadata=metadata
        )

    async def close(self):
        if hasattr(self, 'llm_client') and self.llm_client:
            await self.llm_client.close()


class SimpleRAGSplitter(RAGSplitter):

    def __init__(self):
        self.token_counter = TokenCounter()
        self.logger = logging.getLogger(__name__)

    async def split_by_semantics(self,
                                 text: str,
                                 chunk_size: int = 500,
                                 overlap: int = 50) -> List[Chunk]:
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        chunks = []
        chunk_id = 0
        current_chunk = []
        current_tokens = 0

        for para_idx, paragraph in enumerate(paragraphs):
            para_tokens = self.token_counter.count_tokens(paragraph)

            if current_tokens + para_tokens <= chunk_size:
                current_chunk.append(paragraph)
                current_tokens += para_tokens
            else:
                if current_chunk:
                    chunk = self._create_chunk(
                        chunk_id=chunk_id,
                        content="\n\n".join(current_chunk),
                        start_para=para_idx - len(current_chunk),
                        end_para=para_idx - 1,
                        chunk_size=chunk_size,
                        overlap=overlap
                    )
                    chunks.append(chunk)
                    chunk_id += 1

                current_chunk = [paragraph]
                current_tokens = para_tokens

        if current_chunk:
            chunk = self._create_chunk(
                chunk_id=chunk_id,
                content="\n\n".join(current_chunk),
                start_para=len(paragraphs) - len(current_chunk),
                end_para=len(paragraphs) - 1,
                chunk_size=chunk_size,
                overlap=overlap
            )
            chunks.append(chunk)

        self.logger.info(f"简单分割完成，共生成{len(chunks)}个chunks")
        return chunks

    def _create_chunk(self,
                      chunk_id: int,
                      content: str,
                      start_para: int,
                      end_para: int,
                      chunk_size: int,
                      overlap: int) -> Chunk:
        metadata = {
            "chunk_size": chunk_size,
            "overlap": overlap,
            "start_paragraph": start_para,
            "end_paragraph": end_para,
            "token_count": self.token_counter.count_tokens(content),
            "char_count": len(content),
            "split_method": "simple_paragraph"
        }

        return Chunk(
            content=content,
            chunk_id=chunk_id,
            metadata=metadata
        )


class RagSegmenter:

    def __init__(self,
                 use_llm_splitting: bool = True,
                 llm_backend: str = "deepseek",
                 llm_model: str = "qwen2.5:7b",
                 llm_timeout: int = 300):
        """
        初始化RAG分段器
        Args:
            use_llm_splitting: 是否使用LLM进行语义分割
            llm_backend: LLM后端类型，"ollama" 或 "deepseek"
            llm_model: 使用的模型名称
            llm_timeout: 请求超时时间
        """
        self.use_llm_splitting = use_llm_splitting
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        self.llm_timeout = llm_timeout

        if use_llm_splitting:
            self.splitter = LLMRAGSplitter(
                llm_backend=llm_backend,
                llm_model=llm_model,
                llm_timeout=llm_timeout
            )
        else:
            self.splitter = SimpleRAGSplitter()

        self.logger = logging.getLogger(__name__)

    async def segment(self, clean_text: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict]:
        """
        对清洗后的文本进行RAG分段

        Args:
            clean_text: 清洗后的文本
            chunk_size: 每个chunk的最大token数
            overlap: chunk之间的重叠token数

        Returns:
            分段后的JSON列表
        """
        try:
            self.logger.info(f"开始RAG分段，文本长度: {len(clean_text)}字符")
            chunks = await self.splitter.split_by_semantics(
                text=clean_text,
                chunk_size=chunk_size,
                overlap=overlap
            )

            result = self.format_output(chunks)

            self.logger.info(f"RAG分段完成，生成{len(result)}个分段")
            return result

        except Exception as e:
            self.logger.error(f"RAG分段失败: {str(e)}")
            return []

    def format_output(self, chunks: List[Chunk]) -> List[Dict]:
        """格式化输出为JSON列表"""
        return [chunk.to_dict() for chunk in chunks]

    async def close(self):
        """关闭资源"""
        if hasattr(self.splitter, 'close'):
            await self.splitter.close()


_global_segmenter = None


async def get_segmenter(
    use_llm_splitting: bool = True,
    llm_backend: str = "deepseek",
    llm_model: str = "deepseek-chat",
    llm_timeout: int = 300
) -> RagSegmenter:
    """
    获取全局RAG分段器实例
    Args:
        use_llm_splitting: 是否使用LLM进行语义分割
        llm_backend: LLM后端类型，"ollama" 或 "deepseek"
        llm_model: 使用的模型名称
        llm_timeout: 请求超时时间
    Returns:
        RagSegmenter实例
    """
    global _global_segmenter

    if _global_segmenter is not None:
        if (_global_segmenter.use_llm_splitting != use_llm_splitting or
            _global_segmenter.llm_backend != llm_backend or
                _global_segmenter.llm_model != llm_model):
            await _global_segmenter.close()
            _global_segmenter = None

    if _global_segmenter is None:
        _global_segmenter = RagSegmenter(
            use_llm_splitting=use_llm_splitting,
            llm_backend=llm_backend,
            llm_model=llm_model,
            llm_timeout=llm_timeout
        )
    return _global_segmenter
