from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

llm = ChatOllama(model="qwen2.5-coder:7b", temperature=0.4, num_ctx=8192) # Wait, I don't know the exact model name. Let's import MODEL_NAME from config.
