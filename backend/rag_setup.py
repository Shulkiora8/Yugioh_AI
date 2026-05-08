import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_chroma import Chroma
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
from chromadb.utils.data_loaders import ImageLoader        
from config import BASE_DIR, CHROMA_PATH, COLLECTION_NAME

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

def setup_card_rag(index_path=None):
    if index_path is None:
        index_path = os.path.join(BASE_DIR, "faiss_cards_index")
    if not os.path.exists(index_path):
        print(f"Warning: Card RAG index not found at {index_path}")
        return None
    
    print(f"Loading card RAG index from {index_path}...")
    embeddings = OllamaEmbeddings(model="all-minilm:33m")
    vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    return vectorstore.as_retriever()

# --- Visual RAG (ChromaDB) ---

def setup_visual_rag():
    from database import get_connection
    embeddings = OllamaEmbeddings(model="all-minilm:33m")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, visual_description, local_image FROM card_cache WHERE visual_description IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("No visual descriptions found in SQLite.")
        return None

    documents, metadatas, ids = [], [], []
    for card_id, name, desc, img in rows:
        documents.append(desc)
        metadatas.append({"card_id": card_id, "name": name, "image_path": img or ""})
        ids.append(str(card_id))

    print(f"Indexing {len(documents)} cards into ChromaDB...")
    vectorstore = Chroma.from_texts(
        texts=documents,
        embedding=embeddings,
        metadatas=metadatas,
        ids=ids,
        persist_directory=CHROMA_PATH,
        collection_name=COLLECTION_NAME
    )
    return vectorstore.as_retriever(search_kwargs={"k": 3})

def get_visual_retriever():
    embeddings = OllamaEmbeddings(model="all-minilm:33m")
    vectorstore = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )
    return vectorstore.as_retriever(search_kwargs={"k": 3})

def setup_image_rag():
    try:
        
        image_chroma_path = os.path.join(BASE_DIR, "chromadb_images")
        if not os.path.exists(image_chroma_path):
            print(f"Warning: Image RAG index not found at {image_chroma_path}")
            return None
            
        print(f"Loading Image RAG index from {image_chroma_path}...")
        client = PersistentClient(path=image_chroma_path)
        embedding_function = OpenCLIPEmbeddingFunction()
        data_loader = ImageLoader()
        
        collection = client.get_collection(
            name="image_visual_index",
            embedding_function=embedding_function,
            data_loader=data_loader
        )
        return collection
    except Exception as e:
        print(f"Error loading Image RAG: {e}")
        return None

if __name__ == "__main__":
    # Test loading rules
    retriever = setup_rag("SD_RuleBook_EN_10.pdf")
    print("Rules RAG setup complete.")
    
    # Test loading cards
    card_retriever = setup_card_rag()
    if card_retriever:
        print("Card RAG setup complete.")
