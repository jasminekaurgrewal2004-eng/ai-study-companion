"""
pytest-django tests for the four analytics API endpoints.

Run:
    pytest analytics/tests/test_endpoints.py -v
"""
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def client_auth(db):
    """Authenticated Django test client."""
    user = User.objects.create_user(
        username='testuser_analytics', password='testpass123'
    )
    c = Client()
    c.login(username='testuser_analytics', password='testpass123')
    return c, user


@pytest.mark.django_db
def test_review_queue_authenticated(client_auth):
    """GET /api/analytics/review-queue/ returns 200 with queue or warming_up."""
    c, _ = client_auth
    resp = c.get('/api/analytics/review-queue/')
    assert resp.status_code == 200
    data = resp.json()
    # Must have either 'queue' key or 'status' == 'warming_up'
    assert 'queue' in data or data.get('status') == 'warming_up'


@pytest.mark.django_db
def test_review_queue_requires_auth():
    """GET /api/analytics/review-queue/ redirects unauthenticated users."""
    c = Client()
    resp = c.get('/api/analytics/review-queue/')
    assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_confusion_map_authenticated(client_auth):
    """GET /api/analytics/confusion-map/ returns 200 with clusters or warming_up."""
    c, _ = client_auth
    resp = c.get('/api/analytics/confusion-map/')
    assert resp.status_code == 200
    data = resp.json()
    assert 'clusters' in data or data.get('status') == 'warming_up'


@pytest.mark.django_db
def test_confusion_map_requires_auth():
    """GET /api/analytics/confusion-map/ redirects unauthenticated users."""
    c = Client()
    resp = c.get('/api/analytics/confusion-map/')
    assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_risk_score_authenticated(client_auth):
    """GET /api/analytics/risk-score/ returns 200 with risk/band/top_factors."""
    c, _ = client_auth
    resp = c.get('/api/analytics/risk-score/')
    assert resp.status_code == 200
    data = resp.json()
    assert 'risk' in data or data.get('status') == 'warming_up'
    if 'risk' in data:
        assert 'band' in data
        assert data['band'] in ('low', 'medium', 'high')
        assert 'top_factors' in data


@pytest.mark.django_db
def test_risk_score_requires_auth():
    """GET /api/analytics/risk-score/ redirects unauthenticated users."""
    c = Client()
    resp = c.get('/api/analytics/risk-score/')
    assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_log_review_creates_record(client_auth):
    """POST /api/analytics/log-review/ creates a FlashcardReview and returns 201."""
    from core.models import Flashcard, FlashcardReview

    c, user = client_auth
    card = Flashcard.objects.create(
        user=user, front='What is 2+2?', back='4', subject='math'
    )

    payload = json.dumps({'flashcard_id': card.id, 'grade': 3, 'response_time_ms': 2000})
    resp = c.post(
        '/api/analytics/log-review/',
        data=payload,
        content_type='application/json',
    )
    assert resp.status_code == 201
    data = resp.json()
    assert 'review_id' in data
    assert FlashcardReview.objects.filter(pk=data['review_id']).exists()


@pytest.mark.django_db
def test_log_review_requires_auth():
    """POST /api/analytics/log-review/ redirects unauthenticated users."""
    c = Client()
    resp = c.post(
        '/api/analytics/log-review/',
        data=json.dumps({'flashcard_id': 1, 'grade': 3}),
        content_type='application/json',
    )
    assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_log_review_bad_payload(client_auth):
    """POST /api/analytics/log-review/ with missing fields returns 400."""
    c, _ = client_auth
    resp = c.post(
        '/api/analytics/log-review/',
        data=json.dumps({}),
        content_type='application/json',
    )
    assert resp.status_code == 400
