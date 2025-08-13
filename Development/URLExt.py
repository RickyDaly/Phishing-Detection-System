import pandas as pd
import re
from urllib.parse import urlparse
import tldextract
import os

def extract_url_features(url):
    parsed = urlparse(url)
    extracted = tldextract.extract(url)
    domain = extracted.domain
    suffix = extracted.suffix

    sensitive_keywords = ['login', 'signin', 'verify', 'update', 'security', 'account', 'bank', 'confirm', 'password']
    brand_names = ['google', 'facebook', 'paypal', 'apple', 'amazon', 'microsoft']
    shorteners = ['bit.ly', 'goo.gl', 'tinyurl.com', 'ow.ly', 't.co', 'is.gd', 'buff.ly']

    return {
        'url': url,
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

def process_url_dataset(input_csv, output_csv):
    df = pd.read_csv(input_csv)
    if 'url' not in df.columns or 'label' not in df.columns:
        raise ValueError("Input CSV must contain 'url' and 'label' columns")

    features = []
    for _, row in df.iterrows():
        feats = extract_url_features(row['url'])
        feats['label'] = row['label']
        features.append(feats)

    df_out = pd.DataFrame(features)
    df_out.to_csv(output_csv, index=False)
    print(f"URL features with labels saved to {output_csv}")

if __name__ == '__main__':
    process_url_dataset("results_labelled.csv", "url_features.csv")
