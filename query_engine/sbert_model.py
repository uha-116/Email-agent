import json
import os
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


EMBEDDINGS_FILE = "dataset_embeddings.npy"
QUESTIONS_FILE = "dataset_questions.pkl"
DATA_JSON = "data.json"


# =====================================================
# LOAD QUESTIONS FROM data.json
# =====================================================

def load_questions(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = []
    for item in data:
        if "question" in item:
            q = item["question"].strip().lower()
            if q:
                questions.append(q)

    return questions


# =====================================================
# LOAD SBERT MODEL
# =====================================================

def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


# =====================================================
# CREATE OR UPDATE EMBEDDINGS
# =====================================================

def load_or_update_embeddings(model, current_questions):

    if not os.path.exists(EMBEDDINGS_FILE) or not os.path.exists(QUESTIONS_FILE):

        embeddings = model.encode(current_questions, normalize_embeddings=True)

        np.save(EMBEDDINGS_FILE, embeddings)

        with open(QUESTIONS_FILE, "wb") as f:
            pickle.dump(current_questions, f)

        return embeddings

    # Load existing
    old_embeddings = np.load(EMBEDDINGS_FILE)

    with open(QUESTIONS_FILE, "rb") as f:
        old_questions = pickle.load(f)

    # detect new questions
    new_questions = [q for q in current_questions if q not in old_questions]

    if not new_questions:
        return old_embeddings

    new_embeddings = model.encode(new_questions, normalize_embeddings=True)

    updated_embeddings = np.vstack([old_embeddings, new_embeddings])
    updated_questions = old_questions + new_questions

    np.save(EMBEDDINGS_FILE, updated_embeddings)

    with open(QUESTIONS_FILE, "wb") as f:
        pickle.dump(updated_questions, f)

    return updated_embeddings


# =====================================================
# INITIALIZE SBERT SYSTEM
# =====================================================

class SBERTMatcher:

    def __init__(self):

        self.model = load_model()

        dataset_questions = load_questions(DATA_JSON)

        self.dataset_embeddings = load_or_update_embeddings(
            self.model,
            dataset_questions
        )

        with open(QUESTIONS_FILE, "rb") as f:
            self.dataset_questions = pickle.load(f)

    # -------------------------------------------------

    def find_top_matches(self, query, top_k=3):

        query = query.strip().lower()

        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True
        )[0]

        similarities = cosine_similarity(
            [query_embedding],
            self.dataset_embeddings
        )[0]

        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []

        for idx in top_indices:

            results.append({
                "question": self.dataset_questions[idx],
                "score": float(round(similarities[idx], 4))
            })

        return results


