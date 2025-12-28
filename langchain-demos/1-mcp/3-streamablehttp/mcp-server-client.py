import os, json, contextlib
import click, httpx, dotenv, uvicorn
from loguru import logger
from collections.abc import AsyncIterator
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

dotenv.load_dotenv()


async def fetch_weather(city: str) -> dict | None:
    """
    调用 OpenWeather API 获取指定城市的实时天气信息
    
    参数:
        city (str): 城市名称
        
    返回值:
        dict | None: 成功时返回包含天气信息的字典，失败时返回None
    """
    # 构造API请求参数
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": os.getenv("OPENWEATHER_API_KEY"),
        "units": "metric",
        "lang": "zh_cn",
    }
    
    # 发送异步HTTP请求并处理响应
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(url, params=params)
            res.raise_for_status()
            logger.info(f"获取天气数据结果: {res.json()}")
            return res.json()
    except Exception as e:
        logger.error(f"天气查询失败: {e}")
        return None



@click.command()
@click.option("--port", default=3000, help="Port to listen on for HTTP")
def main(port: int):
    app = Server("mcp-weather")

    @app.call_tool()
    async def get_weather(name: str, arguments: dict) -> list[types.TextContent]:
        """
        获取指定城市的天气信息工具函数
        
        参数:
            name (str): 工具名称
            arguments (dict): 包含请求参数的字典，必须包含'location'键表示城市名称
            
        返回:
            list[types.TextContent]: 包含天气信息的文本内容列表
            
        异常:
            ValueError: 当arguments中缺少'location'参数时抛出
            RuntimeError: 当获取天气数据失败时抛出
        """
        city = arguments.get("location")
        if not city:
            raise ValueError("'location' is required")

        # 记录开始获取天气信息的日志
        ctx = app.request_context
        await ctx.session.send_log_message("info", f"Fetching weather for {city}…",
                                           logger="weather", related_request_id=ctx.request_id)

        # 调用天气API获取数据
        weather = await fetch_weather(city)
        if not weather:
            raise RuntimeError("获取天气数据失败")

        # 记录获取天气信息成功的日志
        await ctx.session.send_log_message("info", "Weather data fetched successfully!",
                                           logger="weather", related_request_id=ctx.request_id)

        # 将天气数据转换为文本内容并返回
        return [types.TextContent(type="text", text=json.dumps(weather, ensure_ascii=False, indent=2))]


    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        """
        列出所有可用的工具
        
        Returns:
            list[types.Tool]: 包含所有可用工具的列表，每个工具包含名称、描述和输入模式等信息
        """
        return [types.Tool(
            name="get-weather",
            description="查询指定城市的实时天气（OpenWeather 数据）",
            inputSchema={
                "type": "object",
                "required": ["location"],
                "properties": {
                    "location": {"type": "string", "description": "城市的英文名称，如 'Beijing'"},
                },
            },
        )]

    # 创建会话管理器实例，用于管理HTTP会话状态
    session_manager = StreamableHTTPSessionManager(app=app, event_store=None, stateless=True)


    async def handle(scope: Scope, receive: Receive, send: Send) -> None:
        """
        处理HTTP请求的异步函数
        
        :param scope: ASGI作用域对象，包含请求信息
        :param receive: 接收函数，用于获取请求数据
        :param send: 发送函数，用于发送响应数据
        :return: None
        """
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        """
        应用生命周期管理函数，在应用启动和关闭时执行相关操作
        
        :param _: Starlette应用实例（未使用）
        :return: 异步迭代器
        """
        async with session_manager.run():
            logger.info("Weather MCP server started 🚀")
            yield
            logger.info("Weather MCP server shutting down…")

    # 创建Starlette应用实例，挂载MCP处理函数到/mcp路径，并设置生命周期管理器
    starlette_app = Starlette(debug=False, routes=[Mount("/mcp", app=handle)], lifespan=lifespan)
    # 启动UVicorn服务器运行应用
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)



if __name__ == "__main__":
    main()

# test
# http://localhost:3000/mcp/