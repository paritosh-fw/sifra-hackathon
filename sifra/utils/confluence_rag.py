#!/usr/bin/env python3
"""
Confluence RAG System
Handles document indexing and retrieval using vector embeddings
"""

import os
import pickle
from typing import List, Dict, Optional
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("⚠️  ChromaDB not installed. Run: pip install chromadb sentence-transformers")

from .confluence_loader import ConfluenceLoader, ConfluencePage


class ConfluenceRAG:
    """
    RAG (Retrieval Augmented Generation) system for Confluence documentation
    
    Architecture:
    1. INDEXING PHASE (run once/periodically):
       - Fetch all pages from Confluence
       - Split into chunks
       - Generate embeddings
       - Store in vector database
    
    2. QUERY PHASE (run on every user query):
       - Convert query to embedding
       - Search vector DB for similar chunks
       - Return top-k relevant chunks
       - LLM uses chunks to answer question
    """
    
    def __init__(self, config):
        """Initialize RAG system with configuration"""
        self.config = config
        self.confluence_config = config.confluence
        self.vector_config = self.confluence_config.get('vector_store', {})
        
        # Setup paths
        self.persist_dir = Path(self.vector_config.get('persist_directory', './data/confluence_vectors'))
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Embedding model
        self.embedding_model_name = self.vector_config.get('embedding_model', 'sentence-transformers/all-MiniLM-L6-v2')
        self.embedding_model = None
        
        # Vector store
        self.vector_store = None
        self.collection = None
        
        # Chunking params
        self.chunk_size = self.vector_config.get('chunk_size', 1000)
        self.chunk_overlap = self.vector_config.get('chunk_overlap', 200)
        self.top_k = self.vector_config.get('top_k', 5)
        
        # Initialize components
        self._initialize_embedding_model()
        self._initialize_vector_store()
    
    def _initialize_embedding_model(self):
        """Load sentence transformer model for embeddings"""
        try:
            print(f"🔄 Loading embedding model: {self.embedding_model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            print("✅ Embedding model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading embedding model: {e}")
            raise
    
    def _initialize_vector_store(self):
        """Initialize ChromaDB vector store"""
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB not installed. Run: pip install chromadb sentence-transformers")
        
        try:
            print("🔄 Initializing ChromaDB vector store...")
            self.vector_store = chromadb.PersistentClient(
                path=str(self.persist_dir)
            )
            
            # Get or create collection
            self.collection = self.vector_store.get_or_create_collection(
                name="confluence_docs",
                metadata={"description": "Confluence documentation embeddings"}
            )
            print(f"✅ Vector store initialized (collection: confluence_docs)")
            print(f"📊 Current document count: {self.collection.count()}")
        except Exception as e:
            print(f"❌ Error initializing vector store: {e}")
            raise
    
    def index_confluence_pages(self, root_page_id: Optional[str] = None):
        """
        INDEXING PHASE: Fetch Confluence pages and create vector embeddings
        
        This is the "education" phase - run once or periodically to update knowledge base
        
        Args:
            root_page_id: Root page ID to start indexing from (uses config if not provided)
        """
        print("\n" + "="*80)
        print("🎓 INDEXING PHASE: Building Confluence Knowledge Base")
        print("="*80 + "\n")
        
        # Get root page ID from config if not provided
        if not root_page_id:
            root_page_id = self.confluence_config.get('root_page_id')
        
        if not root_page_id:
            raise ValueError("No root_page_id provided. Set it in config.yaml or pass as argument")
        
        # Step 1: Fetch all pages from Confluence
        print("📥 Step 1: Fetching pages from Confluence...")
        loader = ConfluenceLoader(
            base_url=self.confluence_config['base_url'],
            username=self.confluence_config['username'],
            api_token=self.confluence_config['api_token']
        )
        
        # Test connection first
        if not loader.test_connection():
            raise ConnectionError("Failed to connect to Confluence. Check your credentials.")
        
        # Fetch all pages recursively
        pages = loader.get_all_descendant_pages(root_page_id)
        
        if not pages:
            print("⚠️  No pages found to index")
            return
        
        print(f"\n✅ Fetched {len(pages)} page(s)")
        
        # Step 2: Chunk documents
        print("\n✂️  Step 2: Chunking documents...")
        chunks = self._chunk_documents(pages)
        print(f"✅ Created {len(chunks)} chunk(s)")
        
        # Step 3: Generate embeddings
        print("\n🧮 Step 3: Generating embeddings...")
        embeddings = self._generate_embeddings(chunks)
        print(f"✅ Generated {len(embeddings)} embedding(s)")
        
        # Step 4: Store in vector database
        print("\n💾 Step 4: Storing in vector database...")
        self._store_embeddings(chunks, embeddings)
        
        print("\n" + "="*80)
        print("✅ INDEXING COMPLETE! Knowledge base is ready for queries.")
        print(f"📊 Total chunks indexed: {self.collection.count()}")
        print("="*80 + "\n")
    
    def _chunk_documents(self, pages: List[ConfluencePage]) -> List[Dict]:
        """
        Split pages into smaller chunks for better retrieval
        
        Returns list of chunks with metadata
        """
        chunks = []
        
        for page in pages:
            # Skip empty pages
            if not page.content or len(page.content.strip()) < 50:
                continue
            
            content = page.content
            
            # Simple character-based chunking with overlap
            start = 0
            chunk_id = 0
            
            while start < len(content):
                end = start + self.chunk_size
                chunk_text = content[start:end]
                
                # Don't create tiny chunks at the end
                if len(chunk_text.strip()) < 100 and chunk_id > 0:
                    break
                
                chunks.append({
                    'id': f"{page.page_id}_{chunk_id}",
                    'text': chunk_text,
                    'page_id': page.page_id,
                    'page_title': page.title,
                    'page_url': page.url,
                    'space': page.space,
                    'labels': page.labels or [],
                    'chunk_index': chunk_id
                })
                
                start = end - self.chunk_overlap  # Overlap for context
                chunk_id += 1
        
        return chunks
    
    def _generate_embeddings(self, chunks: List[Dict]) -> List[List[float]]:
        """Generate vector embeddings for chunks using sentence-transformers"""
        texts = [chunk['text'] for chunk in chunks]
        
        # Generate embeddings in batch (more efficient)
        print(f"   Processing {len(texts)} texts...")
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        return embeddings.tolist()
    
    def _store_embeddings(self, chunks: List[Dict], embeddings: List[List[float]]):
        """Store chunks and embeddings in ChromaDB"""
        # Prepare data for ChromaDB
        ids = [chunk['id'] for chunk in chunks]
        documents = [chunk['text'] for chunk in chunks]
        metadatas = [{
            'page_id': chunk['page_id'],
            'page_title': chunk['page_title'],
            'page_url': chunk['page_url'],
            'space': chunk['space'],
            'chunk_index': chunk['chunk_index']
        } for chunk in chunks]
        
        # Add to collection (upsert = update or insert)
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        print(f"✅ Stored {len(chunks)} chunks in vector database")
    
    def query(self, question: str, top_k: Optional[int] = None) -> List[Dict]:
        """
        QUERY PHASE: Search for relevant documents based on question
        
        This is the "retrieval" phase - runs on every user query
        
        Args:
            question: User's question
            top_k: Number of results to return (uses config default if not provided)
            
        Returns:
            List of relevant document chunks with metadata
        """
        if not top_k:
            top_k = self.top_k
        
        # Check if index exists
        if self.collection.count() == 0:
            print("⚠️  No documents in vector store. Run indexing first!")
            return []
        
        print(f"\n🔍 Searching for: '{question}'")
        
        # Generate embedding for query
        query_embedding = self.embedding_model.encode([question])[0].tolist()
        
        # Search vector store
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # Format results
        formatted_results = []
        if results and results['ids']:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'chunk_id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        print(f"✅ Found {len(formatted_results)} relevant chunks")
        
        return formatted_results
    
    def get_context_for_llm(self, question: str, top_k: Optional[int] = None) -> str:
        """
        Get formatted context string to pass to LLM
        
        Args:
            question: User's question
            top_k: Number of results to retrieve
            
        Returns:
            Formatted context string with source citations
        """
        results = self.query(question, top_k)
        
        if not results:
            return "No relevant documentation found."
        
        # Build context with citations
        context_parts = []
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            text = result['text']
            
            context_parts.append(f"""
[Source {i}: {metadata['page_title']}]
URL: {metadata['page_url']}
Content: {text}
""")
        
        return "\n".join(context_parts)
    
    def answer_question(self, question: str, llm_func=None) -> Dict:
        """
        Complete RAG pipeline: Retrieve + Generate answer
        
        Args:
            question: User's question
            llm_func: Optional LLM function to generate answer (if None, just returns context)
            
        Returns:
            Dictionary with answer and sources
        """
        # Retrieve relevant context
        context = self.get_context_for_llm(question)
        
        # If no LLM provided, just return the context
        if not llm_func:
            return {
                'answer': 'Context retrieved. Provide LLM function to generate answer.',
                'context': context,
                'sources': self.query(question)
            }
        
        # Build prompt with context
        prompt = f"""Based on the following Confluence documentation, please answer the question.

{context}

Question: {question}

Answer (based only on the provided documentation):"""
        
        # Generate answer using LLM
        answer = llm_func(prompt)
        
        return {
            'answer': answer,
            'context': context,
            'sources': self.query(question)
        }


def main():
    """Test/demo the RAG system"""
    from sifra.utils.config import Config
    
    config = Config()
    
    # Initialize RAG
    rag = ConfluenceRAG(config)
    
    # Index documents (run once)
    print("Do you want to index documents? (y/n): ", end="")
    if input().lower() == 'y':
        rag.index_confluence_pages()
    
    # Query loop
    print("\n" + "="*80)
    print("💬 Ready for questions! (type 'quit' to exit)")
    print("="*80 + "\n")
    
    while True:
        question = input("\n🤔 Your question: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            break
        
        if not question:
            continue
        
        # Get relevant context
        context = rag.get_context_for_llm(question)
        print("\n" + "="*80)
        print("📚 Retrieved Context:")
        print("="*80)
        print(context)
        print("="*80 + "\n")


if __name__ == "__main__":
    main()

