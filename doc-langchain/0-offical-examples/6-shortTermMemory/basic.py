from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver  

# dev
# agent = create_agent(
#     "gpt-5",
#     tools=[get_user_info],
#     checkpointer=InMemorySaver(),  
# )
# agent.invoke(
#     {"messages": [{"role": "user", "content": "Hi! My name is Bob."}]},
#     {"configurable": {"thread_id": "1"}},  
# )

# prod
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver  
DB_URI = "postgresql://postgres:postgres@localhost:5442/postgres?sslmode=disable"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup() # auto create tables in PostgresSql
    agent = create_agent(
        "gpt-5",
        tools=[get_user_info],
        checkpointer=checkpointer,  
    )