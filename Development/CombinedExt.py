import pandas as pd
import re
import os
from bs4 import BeautifulSoup, Comment
from urllib.parse import urlparse
import tldextract
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# === CONFIG ===
INPUT_CSV = "results_labelled.csv"
HTML_FOLDER = "files"
OUTPUT_CSV = "combined_features.csv"
VECTOR_SIZE = 300
EPOCHS = 40
NUM_THREADS = 200

# === URL FEATURES ===
def extract_url_features(url):
    parsed = urlparse(url)
    extracted = tldextract.extract(url)
    domain = extracted.domain
    suffix = extracted.suffix
    sensitive_keywords = ['login', 'signin', 'verify', 'update', 'security', 'account', 'bank', 'confirm', 'password']
    brand_names = ['google', 'facebook', 'paypal', 'apple', 'amazon', 'microsoft']
    shorteners = ['bit.ly', 'goo.gl', 'tinyurl.com', 'ow.ly', 't.co', 'is.gd', 'buff.ly']
    return {
        'url_length': len(url),
        'has_at_symbol': int('@' in url),
        'double_slash_in_path': int(url.count('//') > 1),
        'has_ip': int(bool(re.match(r"^(?:http[s]?://)?(?:\d{1,3}\.){3}\d{1,3}", url))),
        'count_hyphens': url.count('-'),
        'count_dots': url.count('.'),
        'count_slashes': url.count('/'),
        'count_special_chars': len(re.findall(r'[^\w]', url)),
        'https_in_domain': int('https' in domain),
        'url_depth': len([x for x in parsed.path.split('/') if x]),
        'has_sensitive_keywords': int(any(keyword in url.lower() for keyword in sensitive_keywords)),
        'tld_type': suffix,
        'is_similar_to_brand': int(any(brand in domain.lower() for brand in brand_names)),
        'dash_in_domain': int('-' in domain),
        'digit_count': len(re.findall(r'\d', url)),
        'vowel_ratio': sum(1 for c in url.lower() if c in 'aeiou') / len(url) if len(url) > 0 else 0,
        'is_short_url': int(any(short in url for short in shorteners)),
        'has_hex_chars': int(bool(re.search(r'%[0-9a-fA-F]{2}', url)))
    }

# === HTML FEATURES ===
def extract_html_features(html):
    soup = BeautifulSoup(html, 'lxml')
    features = {}
    def count(tag, attrs={}): return len(soup.find_all(tag, attrs=attrs))
    def exists(tag, attrs={}): return int(bool(soup.find(tag, attrs=attrs)))

    features['has_form'] = exists('form')
    features['form_count'] = count('form')
    features['has_iframe'] = exists('iframe')
    features['iframe_count'] = count('iframe')
    features['has_script'] = exists('script')
    features['script_count'] = count('script')
    features['has_password_input'] = exists('input', {'type': 'password'})
    features['password_input_count'] = count('input', {'type': 'password'})
    features['submit_input_count'] = count('input', {'type': 'submit'})
    features['email_input_count'] = count('input', {'type': 'email'})
    features['hidden_tag_count'] = count('input', {'type': 'hidden'})

    a_tags = soup.find_all('a')
    features['anchor_count'] = len(a_tags)
    features['empty_href_count'] = len([a for a in a_tags if a.get('href') in ('#', '', None)])
    features['https_link_ratio'] = sum('https' in (a.get('href') or '') for a in a_tags) / len(a_tags) if a_tags else 0
    features['external_link_count'] = sum('http' in (a.get('href') or '') for a in a_tags)
    features['internal_link_count'] = sum('http' not in (a.get('href') or '') for a in a_tags)
    features['internal_to_total_ratio'] = features['internal_link_count'] / len(a_tags) if a_tags else 0
    features['external_to_total_ratio'] = features['external_link_count'] / len(a_tags) if a_tags else 0
    features['suspicious_anchor_count'] = sum(any(s in (a.get('href') or '') for s in ['freehost', 'phish', 'login', 'redirect']) for a in a_tags)

    features['onclick_event_count'] = len(re.findall(r'onclick\s*=', html, re.IGNORECASE))
    features['has_js_redirect'] = int(bool(re.search(r'window\.location|window\.open|location\.href', html)))
    features['js_redirect_count'] = len(re.findall(r'window\.location|window\.open|location\.href', html))
    features['right_click_disabled'] = int('contextmenu' in html or 'event.button==2' in html)
    features['has_popup'] = int(bool(re.search(r'alert\s*\(|confirm\s*\(|prompt\s*\(', html)))
    features['popup_count'] = len(re.findall(r'alert\s*\(|confirm\s*\(|prompt\s*\(', html))
    features['submit_to_email'] = int(bool(re.search(r'action\s*=\s*["\']mailto:', html, re.IGNORECASE)))
    features['has_favicon'] = int(bool(soup.find('link', rel='icon') or soup.find('link', rel='shortcut icon')))
    features['has_div_upper'] = int(bool(re.search(r'<DIV[^>]*>', html)))
    features['has_base64'] = int(bool(re.search(r'data:image\/[a-z]+;base64,', html)))
    features['total_line_count'] = len(html.split('\n'))
    features['total_text_length'] = len(soup.get_text(strip=True))
    features['title'] = int(bool(soup.title and soup.title.string))
    features['title_length'] = len(soup.title.string) if soup.title and soup.title.string else 0
    features['meta_description'] = int(bool(soup.find('meta', attrs={'name': 'description'})))
    features['comment_count'] = sum(1 for s in soup.find_all(string=True) if isinstance(s, Comment))
    return features

# === DOM SEQUENCE ITERATIVE ===
def extract_dom_sequence(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    sequence = []
    stack = [(soup, False)]

    while stack:
        node, is_closing = stack.pop()
        if not getattr(node, 'name', None):
            continue
        if is_closing:
            sequence.append(f"</{node.name}>")
        else:
            sequence.append(f"<{node.name}>")
            stack.append((node, True))
            children = list(node.children)
            for child in reversed(children):
                stack.append((child, False))
    return sequence

def prepare_tagged_documents(df):
    tagged_docs = []
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = {
            executor.submit(lambda idx, row: TaggedDocument(
                words=extract_dom_sequence(open(os.path.join(HTML_FOLDER, row['html']), encoding='utf-8', errors='ignore').read()),
                tags=[f'doc_{idx}']
            ), idx, row): idx for idx, row in df.iterrows()
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Preparing DOM sequences"):
            tagged_docs.append(future.result())
    return tagged_docs

def vectorize_dom_sequences(df, model):
    vectors = [None] * len(df)
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = {
            executor.submit(lambda idx, row: (
                idx, model.infer_vector(
                    extract_dom_sequence(open(os.path.join(HTML_FOLDER, row['html']), encoding='utf-8', errors='ignore').read())
                )
            ), idx, row): idx for idx, row in df.iterrows()
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Vectorizing DOM trees"):
            idx, vector = future.result()
            vectors[idx] = vector
    return vectors

# === MAIN ===
def main():
    print("Loading dataset...")
    df = pd.read_csv(INPUT_CSV)
    if not {'url', 'html', 'label'}.issubset(df.columns):
        raise ValueError("CSV must contain 'URL', 'HTML', and 'Labeled' columns")

    # URL features
    print("Extracting URL features...")
    url_features = [extract_url_features(row['url']) for _, row in tqdm(df.iterrows(), total=len(df), desc="URL Features")]
    url_df = pd.DataFrame(url_features)

    # HTML features
    print("Extracting HTML features...")
    def html_feats(row):
        try:
            with open(os.path.join(HTML_FOLDER, row['html']), 'r', encoding='utf-8') as f:
                html = f.read()
            return extract_html_features(html)
        except Exception as e:
            print(f"[HTML ERROR] {row['html']} => {e}")
            return {}

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        html_results = list(tqdm(executor.map(html_feats, [row for _, row in df.iterrows()]), total=len(df), desc="HTML Features"))
    html_df = pd.DataFrame(html_results)

    # DOM features
    print("Preparing DOM tree features...")
    tagged_docs = prepare_tagged_documents(df)

    print("Training Doc2Vec model...")
    model = Doc2Vec(vector_size=VECTOR_SIZE, min_count=2, epochs=EPOCHS, workers=NUM_THREADS)
    model.build_vocab(tagged_docs)
    model.train(tagged_docs, total_examples=model.corpus_count, epochs=model.epochs)

    print("Vectorizing DOM sequences...")
    dom_vectors = vectorize_dom_sequences(df, model)
    dom_df = pd.DataFrame(dom_vectors, columns=[f'dom_feat_{i}' for i in range(VECTOR_SIZE)])

    # Combine all
    print("Combining all features...")
    combined = pd.concat([df[['url', 'label']], url_df, html_df, dom_df], axis=1)

    print("💾 Saving to CSV...")
    combined.to_csv(OUTPUT_CSV, index=False)
    print(f"All features saved to: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
