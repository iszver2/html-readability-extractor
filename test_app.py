import pytest
import json
import base64
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    """Return basic auth headers with default credentials."""
    credentials = base64.b64encode(b'admin:password').decode('utf-8')
    return {'Authorization': f'Basic {credentials}'}


def test_health_endpoint_returns_200(client):
    """Test that health endpoint returns 200 and correct status."""
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'


def test_extract_text_requires_authentication(client):
    """Test that extract-text endpoint returns 401 without authentication."""
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': '<html><body>test</body></html>'}),
        content_type='application/json'
    )
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'Authentication required'


def test_extract_text_with_wrong_credentials(client):
    """Test that extract-text endpoint returns 401 with wrong credentials."""
    credentials = base64.b64encode(b'wrong:credentials').decode('utf-8')
    headers = {'Authorization': f'Basic {credentials}'}
    
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': '<html><body>test</body></html>'}),
        content_type='application/json',
        headers=headers
    )
    assert response.status_code == 401


def test_extract_text_works_with_valid_html(client, auth_headers):
    """Test that extract-text endpoint works with valid HTML."""
    html_content = '<html><body><h1>Test Title</h1><p>Test content</p></body></html>'
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': html_content}),
        content_type='application/json',
        headers=auth_headers
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'text' in data
    assert 'length' in data
    assert isinstance(data['text'], str)
    assert isinstance(data['length'], int)
    assert data['length'] == len(data['text'])


def test_extract_text_removes_script_tags(client, auth_headers):
    """Test that script tags are removed from extracted text."""
    html_content = '<html><body><h1>Title</h1><script>alert("malicious")</script><p>Content</p></body></html>'
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': html_content}),
        content_type='application/json',
        headers=auth_headers
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'alert' not in data['text']
    assert 'script' not in data['text'].lower()


def test_extract_text_removes_style_tags(client, auth_headers):
    """Test that style tags are removed from extracted text."""
    html_content = '<html><head><style>body{color:red;}</style></head><body><p>Content</p></body></html>'
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': html_content}),
        content_type='application/json',
        headers=auth_headers
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'color:red' not in data['text']
    assert 'body{' not in data['text']


def test_extract_text_missing_html_field(client, auth_headers):
    """Test that extract-text returns 400 for missing html field."""
    response = client.post(
        '/extract-text',
        data=json.dumps({}),
        content_type='application/json',
        headers=auth_headers
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_extract_text_no_json_data(client, auth_headers):
    """Test that extract-text returns 400 when no JSON data is provided."""
    response = client.post(
        '/extract-text',
        headers=auth_headers
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_extract_text_empty_html(client, auth_headers):
    """Test that extract-text returns 400 for empty html field."""
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': ''}),
        content_type='application/json',
        headers=auth_headers
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_extract_text_invalid_html_type(client, auth_headers):
    """Test that extract-text returns 400 for non-string html field."""
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': 123}),
        content_type='application/json',
        headers=auth_headers
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_whitespace_normalization(client, auth_headers):
    """Test that whitespace is correctly normalized in extracted text."""
    html_content = '''<html><body>
        <p>Text   with    multiple     spaces</p>
        <p>Text
        with
        newlines</p>
    </body></html>'''
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': html_content}),
        content_type='application/json',
        headers=auth_headers
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    # Multiple spaces should be normalized to single spaces
    assert '   ' not in data['text']
    # Newlines should be normalized to spaces
    assert '\n' not in data['text']


def test_complex_html_extraction(client, auth_headers):
    """Test extraction with complex HTML including multiple unwanted tags."""
    html_content = '''
    <html>
        <head>
            <title>Article</title>
            <script src="analytics.js"></script>
            <style>body{margin:0}</style>
            <meta charset="utf-8">
        </head>
        <body>
            <nav>Navigation</nav>
            <article>
                <h1>Main Title</h1>
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
            </article>
            <footer>Footer</footer>
        </body>
    </html>
    '''
    response = client.post(
        '/extract-text',
        data=json.dumps({'html': html_content}),
        content_type='application/json',
        headers=auth_headers
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'Main Title' in data['text']
    assert 'First paragraph' in data['text']
    assert 'analytics.js' not in data['text']
    assert 'margin:0' not in data['text']
