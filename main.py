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