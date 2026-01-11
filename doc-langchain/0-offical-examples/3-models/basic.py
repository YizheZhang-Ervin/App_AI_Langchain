import os
from langchain_openai import ChatOpenAI
from langchain.chat_models import init_chat_model

# os.environ["OPENAI_API_KEY"] = "sk-..."

# 方法1
# model = ChatOpenAI(model="gpt-4.1")
# 方法2
# model = init_chat_model("gpt-4.1")
# 方法2 + paramaeters
model = init_chat_model(
    "claude-sonnet-4-5-20250929",
    # Kwargs passed to the model:
    temperature=0.7,
    timeout=30,
    max_tokens=1000,
)

response = model.invoke("Why do parrots talk?")

# invoke1
# conversation = [
#     {"role": "system", "content": "You are a helpful assistant that translates English to French."},
#     {"role": "user", "content": "Translate: I love programming."},
#     {"role": "assistant", "content": "J'adore la programmation."},
#     {"role": "user", "content": "Translate: I love building applications."}
# ]
# response = model.invoke(conversation)
# print(response)  # AIMessage("J'adore créer des applications.")

# invoke2
# from langchain.messages import HumanMessage, AIMessage, SystemMessage
# conversation = [
#     SystemMessage("You are a helpful assistant that translates English to French."),
#     HumanMessage("Translate: I love programming."),
#     AIMessage("J'adore la programmation."),
#     HumanMessage("Translate: I love building applications.")
# ]
# response = model.invoke(conversation)
# print(response)  # AIMessage("J'adore créer des applications.")

# stream
# for chunk in model.stream("Why do parrots have colorful feathers?"):
#     print(chunk.text, end="|", flush=True)

# batch
# responses = model.batch([
#     "Why do parrots have colorful feathers?",
#     "How do airplanes fly?",
#     "What is quantum computing?"
# ])
# for response in responses:
#     print(response)

# batch2
# for response in model.batch_as_completed([
#     "Why do parrots have colorful feathers?",
#     "How do airplanes fly?",
#     "What is quantum computing?"
# ]):
#     print(response)

# tool
from langchain.tools import tool
@tool
def get_weather(location: str) -> str:
    """Get the weather at a location."""
    return f"It's sunny in {location}."
model_with_tools = model.bind_tools([get_weather])  
response = model_with_tools.invoke("What's the weather like in Boston?")
for tool_call in response.tool_calls:
    # View tool calls made by the model
    print(f"Tool: {tool_call['name']}")
    print(f"Args: {tool_call['args']}")

# structured output
from pydantic import BaseModel, Field

class Movie(BaseModel):
    """A movie with details."""
    title: str = Field(..., description="The title of the movie")
    year: int = Field(..., description="The year the movie was released")
    director: str = Field(..., description="The director of the movie")
    rating: float = Field(..., description="The movie's rating out of 10")

model_with_structure = model.with_structured_output(Movie)
response = model_with_structure.invoke("Provide details about the movie Inception")
print(response)  # Movie(title="Inception", year=2010, director="Christopher Nolan", rating=8.8)