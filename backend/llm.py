# llm_client.py
import os
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List
from openai import AsyncOpenAI


class LLMClient(ABC):
    """LLM客户端抽象基类"""

    @abstractmethod
    async def generate(self, prompt: str, is_json=False) -> str:
        """生成文本并返回结果"""
        pass

    @abstractmethod
    async def batch_generate(self, prompts: List[str]) -> List[str]:
        """批量生成文本"""
        pass

    @abstractmethod
    async def close(self):
        """关闭会话"""
        pass


class OllamaClient(LLMClient):

    def __init__(self,
                 base_url: str = "http://localhost:12345",
                 model: str = "qwen2.5:7b",
                 timeout: int = 300):
        """
        初始化Ollama客户端
        Args:
            base_url: Ollama服务器地址
            model: 使用的模型
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.client = None
        self.logger = logging.getLogger(__name__)

    async def _get_client(self) -> AsyncOpenAI:
        """获取OpenAI客户端"""
        if self.client is None:
            self.client = AsyncOpenAI(
                base_url=f"{self.base_url}/v1",
                api_key="ollama",
                timeout=self.timeout
            )
        return self.client

    async def generate(self, prompt: str) -> str:
        """生成单个文本"""
        try:
            client = await self._get_client()

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=8000,
                stream=False
            )

            return response.choices[0].message.content.strip()

        except asyncio.TimeoutError:
            self.logger.error(f"Ollama请求超时: {len(prompt)}字符")
            raise
        except Exception as e:
            self.logger.error(f"Ollama生成失败: {str(e)}")
            raise

    async def batch_generate(self, prompts: List[str]) -> List[str]:
        """批量生成文本"""
        tasks = [self.generate(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.close()


class DeepSeekClient(LLMClient):
    """DeepSeek API客户端实现（使用OpenAI兼容接口）"""

    def __init__(self,
                 api_key: str = "",
                 base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat",
                 timeout: int = 300):
        """
        初始化DeepSeek客户端

        Args:
            api_key: DeepSeek API密钥
            base_url: API基础URL
            model: 使用的模型
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未提供")

        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.client = None
        self.logger = logging.getLogger(__name__)

    async def _get_client(self) -> AsyncOpenAI:
        """获取OpenAI客户端"""
        if self.client is None:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self.client

    async def generate(self, prompt: str, is_json=False) -> str:
        """生成单个文本"""
        try:
            client = await self._get_client()
            messages = [{"role": "user", "content": prompt}]

            params = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 8000,
                "stream": False
            }

            if is_json:
                params["response_format"] = {"type": "json_object"}

            response = await client.chat.completions.create(**params)

            return response.choices[0].message.content.strip()

        except asyncio.TimeoutError:
            self.logger.error(f"DeepSeek请求超时: {len(prompt)}字符")
            raise
        except Exception as e:
            self.logger.error(f"DeepSeek生成失败: {str(e)}")
            raise

    async def batch_generate(self, prompts: List[str]) -> List[str]:
        """批量生成文本"""
        tasks = [self.generate(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.close()


class OpenAIClient(LLMClient):
    """通用OpenAI API客户端"""

    def __init__(self,
                 api_key: str = None,
                 base_url: str = "https://api.openai.com/v1",
                 model: str = "gpt-3.5-turbo",
                 timeout: int = 300):
        """
        初始化OpenAI客户端

        Args:
            api_key: OpenAI API密钥
            base_url: API基础URL（支持自定义）
            model: 使用的模型
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API密钥未提供")

        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.client = None
        self.logger = logging.getLogger(__name__)

    async def _get_client(self) -> AsyncOpenAI:
        """获取OpenAI客户端"""
        if self.client is None:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self.client

    async def generate(self, prompt: str) -> str:
        """生成单个文本"""
        try:
            client = await self._get_client()

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=8000,
                stream=False
            )

            return response.choices[0].message.content.strip()

        except asyncio.TimeoutError:
            self.logger.error(f"OpenAI请求超时: {len(prompt)}字符")
            raise
        except Exception as e:
            self.logger.error(f"OpenAI生成失败: {str(e)}")
            raise

    async def batch_generate(self, prompts: List[str]) -> List[str]:
        """批量生成文本"""
        tasks = [self.generate(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.close()
