import os
import re
import logging
from flask import Flask, request, jsonify
from functools import wraps
from readability import Document
from bs4 import BeautifulSoup

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


def remove_unwanted_tags(html):
    """Remove script, style, and other unwanted tags using BeautifulSoup."""
    soup = BeautifulSoup(html, 'lxml')
    
    # Remove unwanted tags
    unwanted_tags = ['script', 'style', 'meta', 'link', 'noscript', 'iframe']
    for tag in unwanted_tags:
        for element in soup.find_all(tag):
            element.decompose()
    
    return str(soup)


def normalize_whitespace(text):
    """Normalize whitespace in the extracted text."""
    # Replace multiple whitespace characters with a single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint without authentication."""
    logger.info(f"Health check from {request.remote_addr}")
    return jsonify({'status': 'healthy'}), 200


@app.route('/extract-text', methods=['POST'])
@requires_auth
def extract_text():
    """Extract main content text from HTML."""
    try:
        # Get JSON data from request
        data = request.get_json()
        
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
        
        # Use readability-lxml to extract main content
        doc = Document(html_content)
        readable_html = doc.summary()
        
        # Remove unwanted tags using BeautifulSoup
        cleaned_html = remove_unwanted_tags(readable_html)
        
        # Extract text from HTML
        soup = BeautifulSoup(cleaned_html, 'lxml')
        text = soup.get_text()
        
        # Normalize whitespace
        normalized_text = normalize_whitespace(text)
        
        # Calculate length
        text_length = len(normalized_text)
        
        logger.info(f"Successfully extracted text (length: {text_length})")
        
        return jsonify({
            'text': normalized_text,
            'length': text_length
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error processing request: {str(e)}'}), 500


if __name__ == '__main__':
    logger.info(f"Starting Flask application on {HOST}:{PORT} (debug={DEBUG})")
    app.run(host=HOST, port=PORT, debug=DEBUG)
