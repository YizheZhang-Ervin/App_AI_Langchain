import json
import os
import sys
from mcp.client.sse import sse_client
from openai import OpenAI
from loguru import logger
import asyncio
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession
from dotenv import load_dotenv
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam

load_dotenv()


class MCPClient:
    """
    MCP客户端类，用于管理与MCP服务器的连接和交互

    该类负责初始化客户端会话、处理聊天循环以及资源清理
    """

    def __init__(self):
        """
        初始化MCP客户端实例

        初始化客户端会话、异步退出栈和OpenAI客户端
        """
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.base_url = os.getenv("BASE_URL")  # 读取 BASE URL,符合OpenAI API Key格式平台均可
        self.openai_api_key = os.getenv("OPEN_API_KEY")  # 读取API Key
        self.model = os.getenv("MODEL")  # 指定模型
        self.client = OpenAI(api_key=self.openai_api_key, base_url=self.base_url)  # 初始化OpenAI客户端实例

    async def connect_to_server(self, sse_url):
        """
        连接到SSE服务器并初始化会话
        
        Args:
            sse_url (str): SSE服务器的URL地址
            
        Returns:
            None: 无返回值，连接信息存储在实例变量中
        """

        # 建立 SSE 连接
        sse_transport = await self.exit_stack.enter_async_context(sse_client(sse_url))
        self.session = await self.exit_stack.enter_async_context(ClientSession(*sse_transport))
        await self.session.initialize()
        tools = (await self.session.list_tools()).tools
        logger.info(f"已连接 SSE 服务器，支持工具: {[t.name for t in tools]}")

        # 初始化会话
        await self.session.initialize()

        # 列出 MCP 服务器上的工具
        response = await self.session.list_tools()
        tools = response.tools
        logger.info(f"已连接到服务器，支持以下工具:{[tool.name for tool in tools]}")


    async def process_query(self, query: str) -> str:
        """
        处理用户的查询请求，结合大模型和 MCP 工具完成回答。

        该方法首先将用户问题发送给大模型，并根据模型是否需要调用工具来决定下一步流程：
        - 如果模型要求调用工具，则解析工具调用信息并执行对应工具；
        - 执行完成后将结果反馈给模型生成最终回复。

        参数:
            query (str): 用户输入的查询字符串。

        返回:
            str: 模型生成的回答内容。
        """
        messages = [
            ChatCompletionSystemMessageParam(role="system", content="你是一个智能助手，帮助用户回答问题。"),
            ChatCompletionUserMessageParam(role="user", content=query)
        ]

        # 获取 MCP 服务器上可用的工具列表，并转换为模型可识别的格式
        response = await self.session.list_tools()
        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
        } for tool in response.tools]
        # logger.info(f"支持的工具列表{available_tools}")

        # 第一次调用大模型，判断是否需要使用工具
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=available_tools
        )

        # 处理模型返回的内容
        content = response.choices[0]
        if content.finish_reason == "tool_calls":
            # 如果模型决定调用工具，则解析第一个工具调用的信息
            tool_call = content.message.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            # 调用指定工具并记录日志
            result = await self.session.call_tool(tool_name, tool_args)
            logger.info(f"[调用工具] {tool_name} 传入参数是: {tool_args}")

            # 将工具调用请求和执行结果添加到对话历史中
            messages.append(content.message.model_dump())
            messages.append({
                "role": "tool",
                "content": result.content[0].text,
                "tool_call_id": tool_call.id,
            })

            # 将工具执行结果再次传给模型，以生成最终回答
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content

        # 如果不需要调用工具，直接返回模型的回复内容
        return content.message.content

    async def chat_loop(self):
        """
        运行聊天循环

        持续接收用户输入并显示回显，直到用户输入'quit'退出
        支持异常处理以确保程序稳定性
        """
        logger.info("MCP 客户端已启动！")
        print("输入你的问题或输入 'quit' 退出。")

        # 主聊天循环
        while True:
            try:
                query = input("\n🧑‍🦲 [用户输入]: ").strip()

                # 检查退出条件
                if query.lower() == 'quit':
                    break
                # 发送用户输入到 OpenAI API
                response = await self.process_query(query)  # 发送用户输入到 OpenAI API
                print(f"\n🤖 [AI回答] ：{response}")

            except Exception as e:
                print(f"\n⚠️ 发生错误: {str(e)}")

    async def cleanup(self):
        """
        清理资源

        关闭异步退出栈中管理的所有资源
        """
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    sse_url = "http://localhost:8000/sse"
    try:
        await client.connect_to_server(sse_url)
        await client.chat_loop()
    finally:
        # 确保在任何情况下都能正确清理客户端资源
        await client.cleanup()


# 使用asyncio.run()来运行异步主函数main()，确保了异步程序能够正确启动和执行
if __name__ == "__main__":
    asyncio.run(main())
