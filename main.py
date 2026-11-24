import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chromadb
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

app = FastAPI(title="Karnak CPU Local RAG & Agent API")

# 1. إعداد Karnak-6B وموديل Embeddings بإعدادات اقتصادية للـ RAM و CPU
MODEL_NAME = os.getenv("KARNAK_MODEL", "hf.co/mradermacher/Karnak-6B-v1.0-GGUF:Q4_K_M")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")

llm = ChatOllama(
    model=MODEL_NAME,
    temperature=0.2,
    num_ctx=2048,      # تقليل حجم السياق لتوفير الذاكرة
    num_predict=512,   # تحديد سقف لطول الرد لتسريع التوليد على CPU
)
embeddings = OllamaEmbeddings(model=EMBED_MODEL)

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="karnak_docs")

@tool
def search_knowledge_base(query: str) -> str:
    query_vec = embeddings.embed_query(query)
    results = collection.query(query_embeddings=[query_vec], n_results=2)
    docs = results.get("documents", [[]])[0]
    if not docs:
        return "no info"
    return "\n---\n".join(docs)

@tool
def calculate_expression(expression: str) -> str:
    try:
        allowed_chars = set("0123456789+-*/(). ")
        if not set(expression).issubset(allowed_chars):
            return "not allowed"
        return str(eval(expression))
    except Exception as e:
        return f"errir {str(e)}"