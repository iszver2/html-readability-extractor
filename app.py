import os
import re
import html
import logging
from flask import Flask, request, jsonify
from functools import wraps
from bs4 import BeautifulSoup
from inscriptis import get_text
from inscriptis.model.config import ParserConfig

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load configuration from environment variables
USERNAME = os.environ.get('BASIC_AUTH_USERNAME', 'admin')
PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD', 'password')
HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
PORT = int(os.environ.get('FLASK_PORT', '5000'))
DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

# Selectors for OFD receipt content (priority order)
OFD_CONTENT_SELECTORS = [
    '#fido_cheque_container',  # Main receipt container (HTML-encoded)
    '.check_ctn',              # Check container
    '.js__cheque_fido_constructor',  # Alternative container
]

# Advertising/tracking URL patterns to remove
TRACKING_URL_PATTERNS = [
    r'urlstats\.platformaofd\.ru',
    r'share\.floctory\.com',
    r'cdn1\.platformaofd\.ru/checkmarketing',
    r'cdn1\.platformaofd\.ru/fido-constructor',
    r'page\.link',
    r'mc\.yandex\.ru',
    r'jivosite\.com',
    r'besteml\.com',
]

# Patterns for URLs to keep
KEEP_URL_PATTERNS = [
    r'/web/noauth/cheque/pdf',
    r'nalog\.gov\.ru',
    r'platformaofd\.ru/web/noauth/cheque/search',
]


def check_auth(username, password):
    """Check if a username/password combination is valid."""
    return username == USERNAME and password == PASSWORD


def authenticate():
    """Send a 401 response that enables basic auth."""
    return jsonify({'error': 'Authentication required'}), 401, {
        'WWW-Authenticate': 'Basic realm="Login Required"'
    }


def requires_auth(f):
    """Decorator to require basic authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            logger.warning(f"Authentication failed for {request.remote_addr}")
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def remove_advertising_blocks(soup):
    """Remove advertising and promotional blocks by CSS selectors."""
    for selector in AD_SELECTORS:
        for element in soup.select(selector):
            element.decompose()
    return soup


def remove_unwanted_tags(soup):
    """Remove script, style, and other unwanted tags."""
    unwanted_tags = ['script', 'style', 'meta', 'link', 'noscript', 'iframe', 'svg', 'img']
    for tag in unwanted_tags:
        for element in soup.find_all(tag):
            element.decompose()
    return soup


def remove_html_comments(html_str):
    """Remove HTML comments."""
    return re.sub(r'<!--.*?-->', '', html_str, flags=re.DOTALL)


def filter_urls(text):
    """Remove tracking URLs but keep important ones (PDF, FNS)."""
    lines = text.split('\n')
    filtered_lines = []

    for line in lines:
        # Check if line contains a URL
        url_match = re.search(r'https?://[^\s<>"]+', line)
        if url_match:
            url = url_match.group()
            # Check if it's a tracking URL to remove
            is_tracking = any(re.search(pattern, url) for pattern in TRACKING_URL_PATTERNS)
            is_keep = any(re.search(pattern, url) for pattern in KEEP_URL_PATTERNS)

            if is_tracking and not is_keep:
                # Remove the URL from the line
                line = re.sub(r'https?://[^\s<>"]+', '', line)

        filtered_lines.append(line)

    return '\n'.join(filtered_lines)


def extract_important_links(soup):
    """Extract important links (PDF, check verification) before processing."""
    links = {}

    for a in soup.find_all('a', href=True):
        href = a['href']
        # PDF link - prioritize receipt PDF over oferta
        if '/cheque/pdf' in href and 'oferta' not in href.lower():
            links['pdf'] = href
        # FNS verification
        elif 'nalog.gov.ru' in href:
            links['fns'] = href

    return links


def normalize_whitespace(text):
    """Normalize whitespace while preserving structure."""
    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove trailing whitespace on each line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def clean_extracted_text(text):
    """Additional cleaning of extracted text."""
    # Remove common noise patterns (promotional/advertising text)
    noise_patterns = [
        r'Вам подарки за проведенную оплату!?',
        r'Вам доступен \(\d+\) подарок за покупку!?',
        r'Подарок за оплату\s*',
        r'Выбрать подарок\s*',
        r'Забрать\s*',
        r'Активировать\s*',
        r'Ваш подарок за покупку неактивен\s*',
        r'волна',  # decorative image alt text
        r'Картинка',  # decorative image alt text
        r'⭐️[^⭐]*⭐️',  # Emoji-wrapped promo text
    ]

    for pattern in noise_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # Normalize whitespace: collapse multiple spaces/newlines
    text = re.sub(r'\n{2,}', '\n', text)
    text = re.sub(r' {2,}', ' ', text)

    # Remove leading/trailing whitespace from each line and filter empty
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    return '\n'.join(lines)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint without authentication."""
    logger.info(f"Health check from {request.remote_addr}")
    return jsonify({'status': 'healthy'}), 200


def extract_ofd_content(soup):
    """Extract OFD receipt content from specific containers."""
    # Try to find OFD-specific content containers
    for selector in OFD_CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container:
            # For fido_cheque_container, content is HTML-encoded text
            if 'fido' in selector:
                inner_html = container.get_text()
                if inner_html and len(inner_html) > 100:
                    # Decode HTML entities and parse
                    decoded = html.unescape(inner_html)
                    return BeautifulSoup(decoded, 'lxml')
            else:
                return container
    return None


@app.route('/extract-text', methods=['POST'])
@requires_auth
def extract_text():
    """Extract main content text from HTML."""
    try:
        # Get JSON data from request
        data = request.get_json(silent=True)

        if not data:
            logger.error("No JSON data provided")
            return jsonify({'error': 'No JSON data provided'}), 400

        if 'html' not in data:
            logger.error("Missing 'html' field in request")
            return jsonify({'error': "Missing 'html' field in request"}), 400

        html_content = data['html']

        if not html_content or not isinstance(html_content, str):
            logger.error("Invalid 'html' field")
            return jsonify({'error': "Invalid 'html' field"}), 400

        logger.info(f"Processing HTML content from {request.remote_addr} (length: {len(html_content)})")

        # Decode HTML entities in the input
        html_content = html.unescape(html_content)

        # Remove HTML comments first
        html_content = remove_html_comments(html_content)

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'lxml')

        # Extract important links before removing elements
        important_links = extract_important_links(soup)

        # Try to extract OFD-specific content first
        content_soup = extract_ofd_content(soup)

        if content_soup:
            logger.info("Found OFD receipt container")
            soup = content_soup

        # Remove unwanted tags
        soup = remove_unwanted_tags(soup)

        # Get cleaned HTML
        cleaned_html = str(soup)

        # Use inscriptis to convert HTML to text with table structure
        config = ParserConfig(display_links=False, display_anchors=False)
        text = get_text(cleaned_html, config)

        # Filter out tracking URLs
        text = filter_urls(text)

        # Clean extracted text from noise
        text = clean_extracted_text(text)

        # Normalize whitespace
        text = normalize_whitespace(text)

        # Append important links at the end
        if important_links:
            text += '\n\n--- Ссылки ---'
            if 'pdf' in important_links:
                text += f'\nPDF чека: {important_links["pdf"]}'
            if 'fns' in important_links:
                text += f'\nПроверка ФНС: {important_links["fns"]}'

        # Calculate length
        text_length = len(text)

        logger.info(f"Successfully extracted text (length: {text_length})")

        return jsonify({
            'text': text,
            'length': text_length,
            'links': important_links
        }), 200

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error processing request: {str(e)}'}), 500


if __name__ == '__main__':
    logger.info(f"Starting Flask application on {HOST}:{PORT} (debug={DEBUG})")
    app.run(host=HOST, port=PORT, debug=DEBUG)
