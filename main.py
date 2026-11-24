import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import chromadb
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent