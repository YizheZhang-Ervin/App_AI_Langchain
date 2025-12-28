import json
import os
from typing import Any
import httpx
import dotenv
from mcp.server.fastmcp import FastMCP
from loguru import logger

# 加载环境变量配置
dotenv.load_dotenv()

# 初始化 MCP 服务器，命名为 WeatherServer
mcp = FastMCP("WeatherServer")


@mcp.tool()  # 将函数注册为MCP工具
async def get_weather(city: str) -> dict[str, Any] | None:
    """
    查询指定城市的即时天气信息。

    :param city: 必要参数，字符串类型，表示要查询天气的城市名称。
                 注意：中国城市需使用其英文名称，如 "Beijing" 表示北京。
    :return: 返回 OpenWeather API 的响应结果，URL 为
             https://api.openweathermap.org/data/2.5/weather。
             响应内容为 JSON 格式的字典，包含详细的天气数据；
             如果请求失败则返回 None。
    """
    # 构建请求 URL
    url = "https://api.openweathermap.org/data/2.5/weather"

    # 设置查询参数
    params = {
        "q": city,  # 城市名称
        "appid": os.getenv("OPENWEATHER_API_KEY"),  # 从环境变量中读取 API Key
        "units": "metric",  # 使用摄氏度作为温度单位
        "lang": "zh_cn"  # 返回简体中文的天气描述
    }

    # 发起异步 HTTP GET 请求并处理响应
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            logger.info(f"查询天气结果：{json.dumps(response.json())}")
            return response.json()
        except Exception as e:
            logger.error(f"查询天气失败：{e}")
            return None


if __name__ == "__main__":
    # 启动 MCP 服务器，使用标准输入输出方式进行通信
    logger.info("启动 MCP 服务器...")
    mcp.run(transport='stdio')

# 启动
# npx -y @modelcontextprotocol/inspector uv run server.py
# mcp dev mcp-server.py
# cherry studio参数配置
# --directory
# D:\PycharmProjects\LangChainDemo # 替换为实际项目路径
# run
# mcp-server.py