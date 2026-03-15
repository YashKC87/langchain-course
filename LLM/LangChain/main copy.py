import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch

# Load .env from the script folder first, then from nested course folder if present.
_base_dir = Path(__file__).resolve().parent
for _dotenv_file in (_base_dir / ".env", _base_dir / "langchain-course" / ".env"):
    if _dotenv_file.exists():
        load_dotenv(dotenv_path=_dotenv_file)
        break

if not os.getenv("TAVILY_API_KEY"):
    raise RuntimeError(
        "TAVILY_API_KEY is missing. Add it to your .env file.\n"
        "Get a free key at https://app.tavily.com"
    )

search = TavilySearch(max_results=5)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is missing. Add it to your .env file or environment variables."
    )

llm = ChatOpenAI(model="gpt-3.5-turbo", api_key=openai_api_key, temperature=0)
ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
ollama_llm = ChatOllama(model=ollama_model, temperature=0)
tools = [search]
agent = create_agent(model=llm, tools=tools)
ollama_agent = create_agent(model=ollama_llm, tools=tools)


def main():
    print("Using OpenAI model: gpt-3.5-turbo")
    question = "What is the weather in Tokyo?"

    try:
        result = agent.invoke({"messages": [HumanMessage(content=question)]})
        print(result)
    except Exception as exc:
        print("Failed to call OpenAI gpt-3.5-turbo model.")
        print("Verify OPENAI_API_KEY, model access, and account quota.")
        print(f"Details: {exc}")
        print(f"Falling back to local Ollama model: {ollama_model}")

        try:
            result = ollama_agent.invoke({"messages": [HumanMessage(content=question)]})
            print(result)
            return
        except Exception as ollama_exc:
            if "does not support tools" in str(ollama_exc).lower():
                print("Ollama model does not support tools; using direct local chat.")
                response = ollama_llm.invoke(question)
                print(response.content)
                return

            print("Failed to call local Ollama fallback.")
            print(f"Try: `ollama pull {ollama_model}`")
            print(f"Details: {ollama_exc}")


if __name__ == "__main__":
    main()
