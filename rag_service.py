# rag_service.py

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import re

FAISS_INDEX_PATH = "faiss_index"


class RAGService:
    def __init__(self):
        """
        Loads the embedding model and FAISS index into memory on startup.
        This is efficient as it's done only once.
        """
        print("Loading embedding model for RAG Service...")
        self.embeddings = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')
        
        print("Loading FAISS index...")
        try:
            self.db = FAISS.load_local(FAISS_INDEX_PATH, self.embeddings, allow_dangerous_deserialization=True)
            print("FAISS index loaded successfully.")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not load FAISS index. RAG features will be disabled. Error: {e}")
            self.db = None

    # THIS FUNCTION IS NOW CORRECTLY INDENTED AS A METHOD OF THE CLASS
    def retrieve_context(self, query: str, k: int = 2) -> list[tuple[dict, float]]:
        """
        Retrieves the top-k most relevant document chunks for a given query.
        Returns a list of tuples, each containing the document metadata and a normalized similarity score (0 to 1).
        """
        if self.db is None:
            return []
        
        try:
            # Use the more fundamental function that returns L2 distance (lower is better).
            results_with_scores = self.db.similarity_search_with_score(query, k=k)
            
            formatted_results = []
            for doc, score in results_with_scores:
                # Manually normalize the distance score to a similarity score (0 to 1, higher is better).
                similarity_score = 1.0 / (1.0 + score)

                clean_source_id = "Unknown"
                # Robust regex parser for the source ID
                match = re.search(r"Source ID:(.*?)Title:", doc.page_content, re.DOTALL | re.IGNORECASE)
                if match:
                    raw_id = match.group(1)
                    clean_source_id = re.sub(r'\s+', '', raw_id)

                result_item = {
                    "content": doc.page_content,
                    "source": clean_source_id
                }

                # Crucially, cast the final score to a standard Python float to prevent serialization errors.
                formatted_results.append((result_item, float(similarity_score)))

            return formatted_results
        except Exception as e:
            print(f"ERROR during RAG retrieval: {e}")
            return []

# Create a single, global instance of the RAG service to be used by the app
rag_service = RAGService()