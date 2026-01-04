# prompt_templates.py
from typing import Dict, Any


class PromptTemplates:
    """提示词模板管理类"""

    @staticmethod
    def get_clean_prompt(text: str) -> str:
        """
        获取文本清洗的提示词

        Args:
            text: 需要清洗的文本

        Returns:
            完整的提示词
        """
        system_prompt = "请去除以下文段的markdown标记与非文本的部分，并合理补充推断因为ocr识别错误的部分，并按照语义进行分段，每段约500token"
        return f"{system_prompt}\n\n原文：\n{text}"

    @staticmethod
    def get_clean_prompt_with_custom_instruction(text: str, custom_instruction: str = None) -> str:
        """
        获取带有自定义指令的文本清洗提示词
        Args:
            text: 需要清洗的文本
            custom_instruction: 自定义指令
        Returns:
            完整的提示词
        """
        base_instruction = "请去除以下文段的markdown标记与非文本的部分，并合理补充推断因为ocr识别错误的部分，并按照语义进行分段，每段约500token"

        if custom_instruction:
            full_instruction = f"{base_instruction}\n{custom_instruction}"
        else:
            full_instruction = base_instruction

        return f"{full_instruction}\n\n原文：\n{text}"

    @staticmethod
    def get_deepseek_messages(text: str) -> list:
        """
        获取DeepSeek API所需的消息格式

        Args:
            text: 需要清洗的文本

        Returns:
            messages列表
        """
        return [
            {
                "role": "system",
                "content": "请去除以下文段的markdown标记，并合理补充推断因为ocr识别错误的部分，并按照语义进行分段。"
            },
            {
                "role": "user",
                "content": text
            }
        ]
