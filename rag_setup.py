import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

def setup_rag(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
    
    print(f"Loading rules from {pdf_path}...")
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    
    print("Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )
    docs = text_splitter.split_documents(documents)
    
    print("Creating vector store...")
    embeddings = OllamaEmbeddings(model="all-minilm:33m")
    vectorstore = FAISS.from_documents(docs, embeddings)
    
    # Save local if needed, but for now we keep it in memory or return it
    return vectorstore.as_retriever()

if __name__ == "__main__":
    # Test loading
    retriever = setup_rag("SD_RuleBook_EN_10.pdf")
    print("RAG setup complete.")
