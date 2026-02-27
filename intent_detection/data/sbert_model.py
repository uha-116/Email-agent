import json
import os
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


EMBEDDINGS_FILE = "dataset_embeddings.npy"
QUESTIONS_FILE = "dataset_questions.pkl"


# -----------------------------
# STEP 1: LOAD QUESTIONS FROM JSON
# -----------------------------

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


# -----------------------------
# STEP 2: LOAD SBERT MODEL
# -----------------------------

def load_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


# -----------------------------
# STEP 3: LOAD OR UPDATE EMBEDDINGS
# -----------------------------

def load_or_update_embeddings(model, current_questions):
    
    # If embeddings don't exist → create from scratch
    if not os.path.exists(EMBEDDINGS_FILE) or not os.path.exists(QUESTIONS_FILE):
        print("No existing embeddings found. Creating new ones...")
        embeddings = model.encode(current_questions, normalize_embeddings=True)
        np.save(EMBEDDINGS_FILE, embeddings)
        with open(QUESTIONS_FILE, "wb") as f:
            pickle.dump(current_questions, f)
        return embeddings

    # Load existing data
    old_embeddings = np.load(EMBEDDINGS_FILE)
    with open(QUESTIONS_FILE, "rb") as f:
        old_questions = pickle.load(f)

    # Detect new questions
    new_questions = [q for q in current_questions if q not in old_questions]

    if not new_questions:
        print("No new questions detected.")
        return old_embeddings

    print(f"Detected {len(new_questions)} new question(s). Embedding only new ones...")

    new_embeddings = model.encode(new_questions, normalize_embeddings=True)

    # Append
    updated_embeddings = np.vstack([old_embeddings, new_embeddings])
    updated_questions = old_questions + new_questions

    # Save updated
    np.save(EMBEDDINGS_FILE, updated_embeddings)
    with open(QUESTIONS_FILE, "wb") as f:
        pickle.dump(updated_questions, f)

    return updated_embeddings


# -----------------------------
# STEP 4: FIND TOP-K SIMILAR QUESTIONS
# -----------------------------

def find_top_k_similar(query, model, dataset_questions, dataset_embeddings, k=5):
    query = query.strip().lower()

    query_embedding = model.encode(
        [query],
        normalize_embeddings=True
    )[0]

    similarities = cosine_similarity(
        [query_embedding],
        dataset_embeddings
    )[0]

    top_indices = np.argsort(similarities)[::-1][:k]

    results = []
    for idx in top_indices:
        results.append({
            "score": round(float(similarities[idx]), 4),
            "question": dataset_questions[idx]
        })

    return results


# -----------------------------
# STEP 5: MAIN RUNNER
# -----------------------------

def main():
    JSON_PATH = "data.json"

    print("Loading questions from data.json...")
    dataset_questions = load_questions(JSON_PATH)
    print(f"Total questions in JSON: {len(dataset_questions)}\n")

    print("Loading SBERT model...")
    model = load_model()

    print("Loading or updating embeddings...")
    dataset_embeddings = load_or_update_embeddings(model, dataset_questions)

    # Reload updated question list to stay consistent
    with open(QUESTIONS_FILE, "rb") as f:
        dataset_questions = pickle.load(f)

    print("\nReady. Type a question (or 'exit'):\n")

    while True:
        user_query = input("user > ").strip()
        if user_query.lower() in ["exit", "quit"]:
            break

        matches = find_top_k_similar(
            user_query,
            model,
            dataset_questions,
            dataset_embeddings,
            k=5
        )

        print("\nTop matches:")
        for m in matches:
            print(f"  score={m['score']}  |  {m['question']}")
        print("-" * 50)


if __name__ == "__main__":
    main()
