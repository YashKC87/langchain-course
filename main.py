import os

from dotenv import load_dotenv

load_dotenv()


def main():
    print("Hello from langchain!")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    print(openai_api_key)


if __name__ == "__main__":
    main()
