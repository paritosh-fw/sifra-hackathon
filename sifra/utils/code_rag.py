#!/usr/bin/env python3
"""
Code RAG System - Semantic search over codebase using embeddings
Similar to confluence_rag.py but for code files
"""

import os
import re
from typing import List, Dict, Optional
from pathlib import Path

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("⚠️  ChromaDB not installed. Run: pip install chromadb sentence-transformers")


class CodeRAG:
    """
    RAG (Retrieval Augmented Generation) system for codebase
    
    Architecture:
    1. INDEXING PHASE (run once/periodically):
       - Walk through codebase files
       - Split into semantic chunks (methods, classes)
       - Generate embeddings
       - Store in vector database
    
    2. QUERY PHASE (run on every user query):
       - Convert query to embedding
       - Search vector DB for similar code chunks
       - Return top-k relevant chunks
       - LLM uses chunks to answer question
    """
    
    def __init__(self, config):
        """Initialize Code RAG system"""
        self.config = config
        self.codebase_path = Path("/Users/paritoshagarwal/code/itildesk_2")
        
        # Setup paths
        self.persist_dir = Path('./data/code_vectors')
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Embedding model (same as confluence for consistency)
        self.embedding_model_name = 'sentence-transformers/all-MiniLM-L6-v2'
        self.embedding_model = None
        
        # Vector store
        self.vector_store = None
        self.collection = None
        
        # Chunking params
        self.chunk_size = 1200  # Larger to capture complete methods/configs
        self.chunk_overlap = 150
        self.top_k = 10
        
        # Special chunk sizes for different file types
        self.yaml_chunk_size = 2000  # Larger for YAML to capture complete config sections
        
        # File patterns to index
        self.include_patterns = ['*.rb', '*.py', '*.js', '*.yml', '*.yaml']
        self.exclude_dirs = ['.git', 'node_modules', 'tmp', 'log', 'coverage', '__pycache__', 
                            'vendor/bundle', 'public/packs', 'spec', 'test']
        
        # Initialize
        self._initialize_embedding_model()
        self._initialize_vector_store()
    
    def _initialize_embedding_model(self):
        """Load sentence transformer model"""
        try:
            print(f"🔄 Loading embedding model: {self.embedding_model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            print("✅ Embedding model loaded")
        except Exception as e:
            print(f"❌ Error loading embedding model: {e}")
            raise
    
    def _initialize_vector_store(self):
        """Initialize ChromaDB vector store"""
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB not installed")
        
        try:
            print("🔄 Initializing ChromaDB for code...")
            self.vector_store = chromadb.PersistentClient(path=str(self.persist_dir))
            
            self.collection = self.vector_store.get_or_create_collection(
                name="code_embeddings",
                metadata={"description": "ITILDesk codebase embeddings"}
            )
            print(f"✅ Vector store initialized")
            print(f"📊 Current code chunks: {self.collection.count()}")
        except Exception as e:
            print(f"❌ Error initializing vector store: {e}")
            raise
    
    def index_codebase(self, max_files: Optional[int] = None):
        """
        INDEXING PHASE: Index entire codebase with embeddings
        
        Args:
            max_files: Limit number of files (for testing)
        """
        print("\n" + "="*80)
        print("🎓 INDEXING CODEBASE")
        print("="*80 + "\n")
        
        # Step 1: Collect files
        print("📂 Step 1: Collecting code files...")
        files = self._collect_files(max_files)
        print(f"✅ Found {len(files)} files to index")
        
        # Step 2: Extract chunks
        print("\n✂️  Step 2: Extracting code chunks...")
        chunks = self._extract_code_chunks(files)
        print(f"✅ Extracted {len(chunks)} code chunks")
        
        # Step 3: Generate embeddings
        print("\n🧮 Step 3: Generating embeddings...")
        embeddings = self._generate_embeddings(chunks)
        print(f"✅ Generated {len(embeddings)} embeddings")
        
        # Step 4: Store in vector DB
        print("\n💾 Step 4: Storing in vector database...")
        self._store_embeddings(chunks, embeddings)
        
        print("\n" + "="*80)
        print("✅ INDEXING COMPLETE!")
        print(f"📊 Total chunks: {self.collection.count()}")
        print("="*80 + "\n")
    
    def _collect_files(self, max_files: Optional[int] = None) -> List[Path]:
        """Walk codebase and collect files"""
        files = []
        
        for root, dirs, filenames in os.walk(self.codebase_path):
            # Exclude directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for filename in filenames:
                # Check file pattern
                if not any(Path(filename).match(pattern) for pattern in self.include_patterns):
                    continue
                
                file_path = Path(root) / filename
                files.append(file_path)
                
                if max_files and len(files) >= max_files:
                    return files
        
        return files
    
    def _extract_code_chunks(self, files: List[Path]) -> List[Dict]:
        """
        Extract semantic chunks from code files
        
        For Ruby: Extract methods, classes
        For YAML: Extract feature definitions
        For others: Use sliding window
        """
        chunks = []
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                rel_path = file_path.relative_to(self.codebase_path)
                
                # Ruby files: Try to extract methods/classes
                if file_path.suffix == '.rb':
                    file_chunks = self._chunk_ruby_file(content, str(rel_path))
                # YAML files: Extract by sections
                elif file_path.suffix in ['.yml', '.yaml']:
                    file_chunks = self._chunk_yaml_file(content, str(rel_path))
                # Other files: Sliding window
                else:
                    file_chunks = self._chunk_generic_file(content, str(rel_path))
                
                chunks.extend(file_chunks)
                
            except Exception as e:
                print(f"⚠️  Error processing {file_path}: {e}")
                continue
        
        return chunks
    
    def _chunk_ruby_file(self, content: str, file_path: str) -> List[Dict]:
        """Extract Ruby methods and classes as chunks"""
        chunks = []
        lines = content.split('\n')
        
        # Patterns for Ruby methods and classes
        class_pattern = r'^\s*class\s+(\w+)'
        module_pattern = r'^\s*module\s+(\w+)'
        method_pattern = r'^\s*def\s+(\w+)'
        
        current_chunk = []
        current_name = None
        current_type = None
        start_line = 0
        indent_level = 0
        
        for i, line in enumerate(lines):
            # Check for class/module/method start
            class_match = re.match(class_pattern, line)
            module_match = re.match(module_pattern, line)
            method_match = re.match(method_pattern, line)
            
            if class_match or module_match or method_match:
                # Save previous chunk
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    if len(chunk_text.strip()) > 50:
                        chunks.append({
                            'id': f"{file_path}:{start_line}",
                            'text': chunk_text,
                            'file': file_path,
                            'start_line': start_line,
                            'end_line': i,
                            'name': current_name,
                            'type': current_type
                        })
                
                # Start new chunk
                current_chunk = [line]
                start_line = i + 1
                indent_level = len(line) - len(line.lstrip())
                
                if class_match:
                    current_name = class_match.group(1)
                    current_type = 'class'
                elif module_match:
                    current_name = module_match.group(1)
                    current_type = 'module'
                elif method_match:
                    current_name = method_match.group(1)
                    current_type = 'method'
            else:
                current_chunk.append(line)
        
        # Save last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            if len(chunk_text.strip()) > 50:
                chunks.append({
                    'id': f"{file_path}:{start_line}",
                    'text': chunk_text,
                    'file': file_path,
                    'start_line': start_line,
                    'end_line': len(lines),
                    'name': current_name,
                    'type': current_type
                })
        
        # If no methods/classes found, chunk generically
        if not chunks:
            return self._chunk_generic_file(content, file_path)
        
        return chunks
    
    def _chunk_yaml_file(self, content: str, file_path: str) -> List[Dict]:
        """
        Chunk YAML files by top-level keys
        Keep complete sections together for better context
        """
        chunks = []
        lines = content.split('\n')
        
        current_chunk = []
        start_line = 0
        current_key = None
        
        for i, line in enumerate(lines):
            # Top-level key (no indentation at start)
            if line and len(line) > 0 and not line[0].isspace() and ':' in line and not line.startswith('#'):
                # Save previous chunk (only if not too large)
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    # Keep complete sections together unless too large
                    if len(chunk_text.strip()) > 30 and len(chunk_text) < self.yaml_chunk_size * 2:
                        chunks.append({
                            'id': f"{file_path}:{start_line}",
                            'text': chunk_text,
                            'file': file_path,
                            'start_line': start_line,
                            'end_line': i,
                            'name': current_key,
                            'type': 'yaml_section'
                        })
                    elif len(chunk_text) >= self.yaml_chunk_size * 2:
                        # Section too large, split it
                        sub_chunks = self._split_large_yaml_section(chunk_text, file_path, start_line, current_key)
                        chunks.extend(sub_chunks)
                
                # Start new chunk
                current_chunk = [line]
                start_line = i + 1
                current_key = line.split(':')[0].strip()
            else:
                current_chunk.append(line)
        
        # Save last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            if len(chunk_text.strip()) > 30:
                if len(chunk_text) < self.yaml_chunk_size * 2:
                    chunks.append({
                        'id': f"{file_path}:{start_line}",
                        'text': chunk_text,
                        'file': file_path,
                        'start_line': start_line,
                        'end_line': len(lines),
                        'name': current_key,
                        'type': 'yaml_section'
                    })
                else:
                    sub_chunks = self._split_large_yaml_section(chunk_text, file_path, start_line, current_key)
                    chunks.extend(sub_chunks)
        
        return chunks if chunks else self._chunk_generic_file(content, file_path)
    
    def _split_large_yaml_section(self, content: str, file_path: str, start_line: int, section_name: str) -> List[Dict]:
        """Split large YAML sections into smaller chunks"""
        chunks = []
        lines = content.split('\n')
        
        for i in range(0, len(lines), self.yaml_chunk_size):
            chunk_lines = lines[i:i + self.yaml_chunk_size + self.chunk_overlap]
            chunk_text = '\n'.join(chunk_lines)
            
            if len(chunk_text.strip()) > 30:
                chunks.append({
                    'id': f"{file_path}:{start_line + i}",
                    'text': chunk_text,
                    'file': file_path,
                    'start_line': start_line + i,
                    'end_line': start_line + i + len(chunk_lines),
                    'name': f"{section_name}_part_{i // self.yaml_chunk_size + 1}",
                    'type': 'yaml_section_part'
                })
        
        return chunks
    
    def _chunk_generic_file(self, content: str, file_path: str) -> List[Dict]:
        """Sliding window chunking for generic files"""
        chunks = []
        lines = content.split('\n')
        
        # Chunk by line count
        chunk_lines = 50  # ~50 lines per chunk
        overlap_lines = 5
        
        for i in range(0, len(lines), chunk_lines - overlap_lines):
            chunk_content = '\n'.join(lines[i:i + chunk_lines])
            
            if len(chunk_content.strip()) > 50:
                chunks.append({
                    'id': f"{file_path}:{i+1}",
                    'text': chunk_content,
                    'file': file_path,
                    'start_line': i + 1,
                    'end_line': min(i + chunk_lines, len(lines)),
                    'name': None,
                    'type': 'generic_chunk'
                })
        
        return chunks
    
    def _generate_embeddings(self, chunks: List[Dict]) -> List[List[float]]:
        """Generate embeddings for code chunks"""
        texts = [chunk['text'] for chunk in chunks]
        
        print(f"   Processing {len(texts)} code chunks...")
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True,
            batch_size=32
        )
        
        return embeddings.tolist()
    
    def _store_embeddings(self, chunks: List[Dict], embeddings: List[List[float]]):
        """Store chunks in ChromaDB"""
        ids = [chunk['id'] for chunk in chunks]
        documents = [chunk['text'] for chunk in chunks]
        metadatas = [{
            'file': chunk['file'],
            'start_line': chunk['start_line'],
            'end_line': chunk['end_line'],
            'name': chunk.get('name', ''),
            'type': chunk.get('type', '')
        } for chunk in chunks]
        
        # Batch upsert (ChromaDB has limits)
        batch_size = 1000
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            batch_embeds = embeddings[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            
            self.collection.upsert(
                ids=batch_ids,
                embeddings=batch_embeds,
                documents=batch_docs,
                metadatas=batch_metas
            )
        
        print(f"✅ Stored {len(chunks)} chunks")
    
    def query(self, question: str, top_k: Optional[int] = None) -> List[Dict]:
        """
        QUERY PHASE: Semantic search for relevant code
        
        Args:
            question: Natural language question
            top_k: Number of results
            
        Returns:
            List of relevant code chunks with metadata
        """
        if not top_k:
            top_k = self.top_k
        
        if self.collection.count() == 0:
            print("⚠️  No code indexed. Run index_codebase() first!")
            return []
        
        print(f"\n🔍 Semantic search: '{question}'")
        
        # Generate query embedding
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
        
        print(f"✅ Found {len(formatted_results)} relevant code chunks")
        
        return formatted_results
    
    def get_context_for_llm(self, question: str, top_k: Optional[int] = None) -> str:
        """Get formatted context for LLM"""
        results = self.query(question, top_k)
        
        if not results:
            return "No relevant code found."
        
        context_parts = []
        for i, result in enumerate(results, 1):
            meta = result['metadata']
            text = result['text']
            
            context_parts.append(f"""
[Code {i}: {meta['file']}:{meta['start_line']}-{meta['end_line']}]
Type: {meta.get('type', 'code')}
Name: {meta.get('name', 'N/A')}

```
{text}
```
""")
        
        return "\n".join(context_parts)


def main():
    """Test/demo Code RAG"""
    from sifra.utils.config import Config
    
    config = Config()
    rag = CodeRAG(config)
    
    # Index codebase (run once)
    print("Index codebase? (y/n): ", end="")
    if input().lower() == 'y':
        print("Limit files (for testing)? Enter number or 'all': ", end="")
        limit = input().strip()
        max_files = None if limit.lower() == 'all' else int(limit)
        rag.index_codebase(max_files=max_files)
    
    # Query loop
    print("\n" + "="*80)
    print("💬 Ready for code queries! (type 'quit' to exit)")
    print("="*80 + "\n")
    
    while True:
        question = input("\n🤔 Your question: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            break
        
        if not question:
            continue
        
        # Get relevant code
        context = rag.get_context_for_llm(question, top_k=5)
        print("\n" + "="*80)
        print("📚 Retrieved Code:")
        print("="*80)
        print(context)
        print("="*80 + "\n")


if __name__ == "__main__":
    main()

