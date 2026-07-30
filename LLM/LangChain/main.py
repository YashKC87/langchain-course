from dotenv import load_dotenv
import json
import os
from typing import List
from pydantic import BaseModel, Field
load_dotenv()
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langchain_tavily import TavilySearch

class source(BaseModel):
    """Schema for a source used by the agent"""

    url:str = Field(description="The URL of the source")
class agent_response(BaseModel):
    """Schema for the agent's response"""
    answer:str = Field(description="The answer to the user's question")
    sources:List[source] = Field(default_factory=list, description="List of sources used to answer the question")


def build_structured_response(result: dict) -> agent_response:
    messages = result.get("messages", [])
    answer = ""
    collected_sources: List[source] = []

    for message in reversed(messages):
        if getattr(message, "type", "") == "ai" and getattr(message, "content", ""):
            answer = message.content
            break

    for message in messages:
        if getattr(message, "type", "") != "tool":
            continue

        content = getattr(message, "content", "")
        try:
            payload = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            continue

        for item in payload.get("results", []):
            url = item.get("url")
            if url:
                collected_sources.append(source(url=url))

    unique_sources: List[source] = []
    seen_urls = set()
    for item in collected_sources:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        unique_sources.append(item)

    return agent_response(answer=answer, sources=unique_sources)


llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "gemma3:270m"))
tools = [TavilySearch()]
agent = create_agent(model=llm,tools=tools,response_format=agent_response)



def main():
    print("Hello from Weather agent!")
    result = agent.invoke({"messages":HumanMessage(content="What is weather in India?")})
    result["structured_response"] = build_structured_response(result).model_dump()

    print(result)
    print(result["structured_response"])

if __name__ == "__main__":
    main()