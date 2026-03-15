from dotenv import load_dotenv
import os

load_dotenv()
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from tavily import TavilyClient

tavily_api_key = os.getenv("TAVILY_API_KEY")
tavily = TavilyClient(api_key=tavily_api_key) if tavily_api_key else None

@tool
def search(query: str) -> str:
    """
    Tool that searches over internet
    Args:
        query: The query to search for
    Returns:
        The search result
    """
    print(f"Searching for {query}")
    if tavily is None:
        return "TAVILY_API_KEY is not set. Add it to your .env file to enable web search."
    return tavily.search(query=query)


llm = ChatOllama(model="Qwen3")
tools = [search]
agent = create_agent(model=llm,tools=tools)


def main():
    print("Hello from langchain-course!")
    result = agent.invoke({"messages":HumanMessage(content="What is weather in India?")})
    print(result)

if __name__ == "__main__":
    main()