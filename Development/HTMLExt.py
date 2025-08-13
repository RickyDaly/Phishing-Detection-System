import pandas as pd
import re
import os
import time
from bs4 import BeautifulSoup, Comment
from concurrent.futures import ThreadPoolExecutor, as_completed

def extract_html_features(html):
    soup = BeautifulSoup(html, 'lxml')
    features = {}
    timings = {}

    def timed(tag_name, func):
        start = time.time()
        result = func()
        timings[tag_name] = round(time.time() - start, 4)
        return result

    def count(tag, attrs={}):
        return len(soup.find_all(tag, attrs=attrs))

    def exists(tag, attrs={}):
        return int(bool(soup.find(tag, attrs=attrs)))

    features['has_form'] = timed('has_form', lambda: exists('form'))
    features['form_count'] = timed('form_count', lambda: count('form'))
    features['has_iframe'] = timed('has_iframe', lambda: exists('iframe'))
    features['iframe_count'] = timed('iframe_count', lambda: count('iframe'))
    features['has_script'] = timed('has_script', lambda: exists('script'))
    features['script_count'] = timed('script_count', lambda: count('script'))
    features['has_password_input'] = timed('password_input', lambda: exists('input', {'type': 'password'}))
    features['password_input_count'] = timed('password_input_count', lambda: count('input', {'type': 'password'}))
    features['submit_input_count'] = timed('submit_input_count', lambda: count('input', {'type': 'submit'}))
    features['email_input_count'] = timed('email_input_count', lambda: count('input', {'type': 'email'}))
    features['hidden_tag_count'] = timed('hidden_tag_count', lambda: count('input', {'type': 'hidden'}))

    def anchor_analysis():
        a_tags = soup.find_all('a')
        features['anchor_count'] = len(a_tags)
        features['empty_href_count'] = len([a for a in a_tags if a.get('href') in ('#', '', None)])
        features['https_link_ratio'] = sum('https' in (a.get('href') or '') for a in a_tags) / len(a_tags) if a_tags else 0
        features['external_link_count'] = sum('http' in (a.get('href') or '') for a in a_tags)
        features['internal_link_count'] = sum('http' not in (a.get('href') or '') for a in a_tags)
        features['internal_to_total_ratio'] = features['internal_link_count'] / len(a_tags) if a_tags else 0
        features['external_to_total_ratio'] = features['external_link_count'] / len(a_tags) if a_tags else 0
        features['suspicious_anchor_count'] = sum(any(susp in (a.get('href') or '') for susp in ['freehost', 'phish', 'login', 'redirect']) for a in a_tags)
    timed('anchor_analysis', anchor_analysis)

    features['onclick_event_count'] = timed('onclick_event_count', lambda: len(re.findall(r'onclick\s*=', html, re.IGNORECASE)))
    features['has_js_redirect'] = timed('has_js_redirect', lambda: int(bool(re.search(r'window\.location|window\.open|location\.href', html))))
    features['js_redirect_count'] = timed('js_redirect_count', lambda: len(re.findall(r'window\.location|window\.open|location\.href', html)))
    features['right_click_disabled'] = timed('right_click_disabled', lambda: int('contextmenu' in html or 'event.button==2' in html))
    features['has_popup'] = timed('has_popup', lambda: int(bool(re.search(r'alert\s*\(|confirm\s*\(|prompt\s*\(', html))))
    features['popup_count'] = timed('popup_count', lambda: len(re.findall(r'alert\s*\(|confirm\s*\(|prompt\s*\(', html)))
    features['submit_to_email'] = timed('submit_to_email', lambda: int(bool(re.search(r'action\s*=\s*["\']mailto:', html, re.IGNORECASE))))
    features['has_favicon'] = timed('has_favicon', lambda: int(bool(soup.find('link', rel='icon') or soup.find('link', rel='shortcut icon'))))
    features['has_div_upper'] = timed('has_div_upper', lambda: int(bool(re.search(r'<DIV[^>]*>', html))))
    features['has_base64'] = timed('has_base64', lambda: int(bool(re.search(r'data:image\/[a-z]+;base64,', html))))
    features['total_line_count'] = timed('total_line_count', lambda: len(html.split('\n')))
    features['total_text_length'] = timed('total_text_length', lambda: len(soup.get_text(strip=True)))
    features['title'] = timed('title_presence', lambda: int(bool(soup.title and soup.title.string)))
    features['title_length'] = timed('title_length', lambda: len(soup.title.string) if soup.title and soup.title.string else 0)
    features['meta_description'] = timed('meta_description', lambda: int(bool(soup.find('meta', attrs={'name': 'description'}))))
    features['comment_count'] = timed('comment_count', lambda: sum(1 for s in soup.find_all(string=True) if isinstance(s, Comment)))

    for tag in ['div', 'span', 'style', 'meta', 'img', 'label', 'select', 'audio', 'video',
                'table', 'th', 'tr', 'td', 'li', 'ul', 'p', 'h1', 'h2', 'br', 'option',
                'base', 'address', 'nav', 'figure', 'section', 'canvas', 'button']:
        features[f'{tag}_count'] = timed(f'{tag}_count', lambda tag=tag: count(tag))

    total = sum(timings.values())
    print(" Feature timing (top 5):", sorted(timings.items(), key=lambda x: x[1], reverse=True)[:5], f"| total: {round(total, 2)}s")

    return features

def process_single_row(row, html_folder):
    html_path = os.path.join(html_folder, row['html'])
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        feats = extract_html_features(html)
        feats['label'] = row['label']
        feats['url'] = row['url']  # <--- Here we add the URL
        return feats
    except Exception as e:
        print(f" Error reading {html_path}: {e}")
        return None

def process_html_dataset_threaded(input_csv, output_csv, html_folder="./files", max_workers=10):
    df = pd.read_csv(input_csv)
    if 'html' not in df.columns or 'label' not in df.columns or 'url' not in df.columns:
        raise ValueError("Input CSV must contain 'HTML', 'Phishing', and 'URL' columns")

    results = []

    print(f" Starting multithreaded feature extraction with {max_workers} threads...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_single_row, row, html_folder) for _, row in df.iterrows()]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    df_out = pd.DataFrame(results)
    df_out.to_csv(output_csv, index=False)
    print(f"HTML features with labels and URLs saved to {output_csv}")

if __name__ == '__main__':
    process_html_dataset_threaded("results_labelled.csv", "new_html_features_with_url.csv", max_workers=50)
