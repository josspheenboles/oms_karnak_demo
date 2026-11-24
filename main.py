import io
import os
from docx import Document
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
import chromadb
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent


class JudgeScore(BaseModel):
    faithfulness: int = Field(..., ge=1, le=5, description="The extent to which the answer adheres to the context, on a scale of 1 to 5")
    relevance: int = Field(..., ge=1, le=5, description="The relevance of the answer to the question, on a scale of 1 to 5")
    reason: str = Field(..., description="A brief and clear justification for the score")
class EvalRequest(BaseModel):
    question: str
    context: str = ""
    answer: str

KARNAK_JUDGE_MODEL = os.getenv(
    "KARNAK_MODEL",
    "hf.co/mradermacher/Karnak-6B-v1.0-GGUF:Q4_K_M",
)
judge_llm = ChatOllama(
    model=KARNAK_JUDGE_MODEL,
    temperature=0,
    num_ctx=2048,
    num_predict=256,
).with_structured_output(JudgeScore)

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

def extract_docx_text(raw_bytes: bytes) -> str:
    """Extract text from paragraphs and tables in a .docx file."""
    doc = Document(io.BytesIO(raw_bytes))
    parts: list[str] = []

    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())

    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                parts.append(" | ".join(row_cells))

    return "\n".join(parts)

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks for RAG retrieval."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(cleaned):
        chunks.append(cleaned[start : start + chunk_size])
        start += step
    return chunks


@tool(description="Search through stored documents and files to answer user questions.")
def search_knowledge_base(query: str) -> str:
    query_vec = embeddings.embed_query(query)
    results = collection.query(query_embeddings=[query_vec], n_results=2)
    docs = results.get("documents", [[]])[0]
    if not docs:     
        return "no info"
    return "\n---\n".join(docs)

@tool(description="Calculate simple arithmetic operations, such as: 150 * 0.14")
def calculate_expression(expression: str) -> str:
    try:
        allowed_chars = set("0123456789+-*/(). ")
        if not set(expression).issubset(allowed_chars):
            return "not allowed"
        return str(eval(expression))
    except Exception as e:
        return f"errir {str(e)}"

tools = [search_knowledge_base, calculate_expression]
agent_executor = create_react_agent(
    llm,
    tools,
    prompt="You are an intelligent Egyptian assistant who speaks Arabic fluently, concisely, and clearly. Use the available tools whenever necessary."
)

class DocumentInput(BaseModel):
    doc_id: str
    text: str


class ChatRequest(BaseModel):
    query: str

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    allowed_extensions = (".docx", ".txt", ".md", ".csv", ".log")
    filename = file.filename or "uploaded_file.txt"
    lower_name = filename.lower()

    if not lower_name.endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a .docx file or text file (.txt, .md, .csv, .log)."
        )

    try:
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        if lower_name.endswith(".docx"):
            text = extract_docx_text(raw_bytes)
        else:
            text = raw_bytes.decode("utf-8", errors="ignore")

        chunks = chunk_text(text, chunk_size=600, overlap=100)
        if not chunks:
            raise HTTPException(status_code=400, detail="No readable text found in the file.")

        vectors = embeddings.embed_documents(chunks)
        ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]

        collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=chunks,
            metadatas=metadatas,
        )
        return {
            "status": "success",
            "filename": filename,
            "chunks_stored": len(chunks),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/agent/chat")
def chat_with_agent(req: ChatRequest):
    try:
        response = agent_executor.invoke({"messages": [("user", req.query)]})
        final_message = response["messages"][-1].content
        return {"answer": final_message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))