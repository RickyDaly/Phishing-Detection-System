import pandas as pd
from bs4 import BeautifulSoup
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from tqdm import tqdm
import os
from concurrent.futures import ThreadPoolExecutor, as_completed


INPUT_CSV = "results_labelled.csv"
OUTPUT_CSV = "dom_features_output.csv"
HTML_FOLDER = "files"
VECTOR_SIZE = 300
EPOCHS = 40
NUM_THREADS = 8  # Adjust based on your system

def extract_dom_sequence(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    sequence = []

    def traverse(node):
        if node.name:
            sequence.append(f"<{node.name}>")
            for child in node.children:
                traverse(child)
            sequence.append(f"</{node.name}>")
    traverse(soup)
    return sequence

def read_html_and_create_tagged_doc(idx, row):
    try:
        html_path = os.path.join(HTML_FOLDER, row['html'])
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
            tags = extract_dom_sequence(html)
            return TaggedDocument(words=tags, tags=[f'doc_{idx}'])
    except Exception as e:
        print(f"[!] Error reading {html_path}: {e}")
        return None

def prepare_tagged_documents(df):
    tagged_docs = []
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = {executor.submit(read_html_and_create_tagged_doc, idx, row): idx for idx, row in df.iterrows()}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Preparing DOM tag corpus"):
            result = future.result()
            if result is not None:
                tagged_docs.append(result)
    return tagged_docs

def vectorize_html_with_model(idx, row, model):
    try:
        html_path = os.path.join(HTML_FOLDER, row['html'])
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
            tags = extract_dom_sequence(html)
            return model.infer_vector(tags)
    except Exception as e:
        print(f"[!] Error vectorizing {html_path}: {e}")
        return [0.0] * model.vector_size

def vectorize_dom_sequences(df, model):
    vectors = [None] * len(df)
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = {executor.submit(vectorize_html_with_model, idx, row, model): idx for idx, row in df.iterrows()}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Vectorizing DOM trees"):
            idx = futures[future]
            result = future.result()
            vectors[idx] = result
    return vectors

def train_doc2vec(tagged_docs, vector_size=300, epochs=40):
    print(" Training Doc2Vec model...")
    model = Doc2Vec(vector_size=vector_size, min_count=2, epochs=epochs, workers=NUM_THREADS)
    model.build_vocab(tagged_docs)
    model.train(tagged_docs, total_examples=model.corpus_count, epochs=model.epochs)
    return model

def save_vectors_to_csv(df, vectors, output_file):
    vec_df = pd.DataFrame(vectors, columns=[f'dom_feat_{i}' for i in range(len(vectors[0]))])
    final_df = pd.concat([df[['url', 'label']].reset_index(drop=True), vec_df], axis=1)
    final_df.to_csv(output_file, index=False)
    print(f" Feature CSV saved: {output_file}")

def main():
    print(f" Loading dataset: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV)

    if not {'html', 'url', 'label'}.issubset(df.columns):
        raise ValueError(" Input CSV must contain 'HTML', 'URL', and 'Label' columns")

    tagged_docs = prepare_tagged_documents(df)
    model = train_doc2vec(tagged_docs, vector_size=VECTOR_SIZE, epochs=EPOCHS)

    vectors = vectorize_dom_sequences(df, model)
    save_vectors_to_csv(df, vectors, OUTPUT_CSV)

if __name__ == "__main__":
    main()
