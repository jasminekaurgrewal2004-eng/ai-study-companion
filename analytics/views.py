"""
Analytics API — endpoints (all @login_required).

GET  /api/analytics/review-queue/   → {queue: [...]}
GET  /api/analytics/confusion-map/  → {clusters: [...]}
GET  /api/analytics/study-time/     → {peak_window, peak_days, heatmap, message, confidence}
GET  /api/analytics/risk-score/     → {risk, band, top_factors}
POST /api/analytics/log-review/     → 201
GET  /api/analytics/smart-topics/   → {topics: [...]}
GET  /api/analytics/generate-quiz/  → {questions: [...], prediction: {...}}

Universal fallback: any model file missing → 200 {"status": "warming_up"}
"""
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@login_required
@require_http_methods(['GET'])
def review_queue(request):
    """
    Return up to 10 flashcards sorted by lowest predicted recall probability.
    """
    from core.models import Flashcard, FlashcardReview
    from analytics.ml.forgetting_curve import predict_card_recall, _load_model
    from django.utils import timezone

    # Warming-up guard
    model = _load_model()
    # We still return data even without a model (uses exponential fallback)

    now = timezone.now()
    cards = (
        Flashcard.objects.filter(user=request.user)
        .order_by('next_review')[:50]
    )

    queue = []
    for card in cards:
        result = predict_card_recall(card.id, request.user.id)
        if 'status' in result:
            return JsonResponse({'status': 'warming_up'})
        queue.append({
            'flashcard_id': card.id,
            'topic': card.subject,
            'front': card.front[:120],
            'p_recall': result['p_recall'],
            'due_in_days': result['optimal_review_in_days'],
        })

    queue.sort(key=lambda x: x['p_recall'])
    return JsonResponse({'queue': queue[:10]})


@login_required
@require_http_methods(['GET'])
def confusion_map(request):
    """
    Return confusion clusters for the logged-in user's chat history.
    """
    from analytics.ml.confusion_clusters import get_user_clusters, _load_artefacts

    artefacts = _load_artefacts()
    if artefacts is None:
        return JsonResponse({'status': 'warming_up'})

    clusters = get_user_clusters(request.user.id)

    # Flatten warming_up bubbled from wrapper
    if clusters and isinstance(clusters[0], dict) and clusters[0].get('status') == 'warming_up':
        return JsonResponse({'status': 'warming_up'})

    formatted = [
        {
            'label': c['label'],
            'count': c['count'],
            'example': c['example_question'],
            'suggested_action': f"Review your {c['suggested_topic']} notes and practise with flashcards.",
        }
        for c in clusters
        if c.get('label') != 'Other'
    ]
    return JsonResponse({'clusters': formatted})


@login_required
@require_http_methods(['GET'])
def risk_score(request):
    """
    Return at-risk probability + SHAP top-3 factors for the current user.
    """
    from analytics.ml.risk_score import predict_risk, _load_models

    xgb, _ = _load_models()
    if xgb is None:
        # rule-based fallback still works; only mark warming_up if explicitly desired
        pass

    result = predict_risk(request.user.id)
    return JsonResponse(result)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def log_review(request):
    """
    Record a FlashcardReview.

    Body (JSON): {flashcard_id: int, grade: int (0-5), response_time_ms: int}
    Returns: 201 Created
    """
    from core.models import Flashcard, FlashcardReview
    from django.utils import timezone

    try:
        body = json.loads(request.body)
        flashcard_id = int(body['flashcard_id'])
        grade = int(body['grade'])
        response_time_ms = int(body.get('response_time_ms', 0))
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    try:
        card = Flashcard.objects.get(pk=flashcard_id, user=request.user)
    except Flashcard.DoesNotExist:
        return JsonResponse({'error': 'Flashcard not found'}, status=404)

    # Compute days since last review
    last = (
        FlashcardReview.objects.filter(flashcard=card, user=request.user)
        .order_by('-reviewed_at').first()
    )
    now = timezone.now()
    days_since = (
        (now - last.reviewed_at).total_seconds() / 86400
        if last else 0.0
    )

    review = FlashcardReview.objects.create(
        flashcard=card,
        user=request.user,
        grade=grade,
        days_since_last=round(days_since, 4),
        response_time_ms=response_time_ms,
    )

    # Log prediction
    from core.models import PredictionLog
    PredictionLog.objects.create(
        user=request.user,
        feature_name='log_review',
        payload_json={
            'flashcard_id': flashcard_id,
            'grade': grade,
            'response_time_ms': response_time_ms,
            'review_id': review.id,
        },
    )

    return JsonResponse({'review_id': review.id, 'days_since_last': days_since}, status=201)


@login_required
@require_http_methods(['GET'])
def smart_topics(request):
    """
    Return all topics ranked by learning priority (F1 recall + F2 confusion).

    Response: {topics: [{topic, priority, predicted_score_pct, reason}]}
    """
    from analytics.ml.quiz_generator import get_smart_topics
    topics = get_smart_topics(request.user.id)
    return JsonResponse({'topics': topics})


@login_required
@require_http_methods(['GET'])
def generate_quiz(request):
    """
    Generate an AI-powered MCQ quiz for any topic using Groq LLM.

    Query params: topic (str), count (int, default 10, max 20)
    Response: {questions: [...], prediction: {...}, topic: str}
    """
    import os, json as _json, re
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()

    topic = request.GET.get('topic', '').strip()
    if not topic:
        return JsonResponse({'error': 'topic required'}, status=400)
    try:
        count = min(int(request.GET.get('count', 10)), 20)
    except ValueError:
        count = 10

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return JsonResponse({'error': 'Groq API key not configured'}, status=500)

    prompt = f"""Generate exactly {count} multiple-choice quiz questions on the topic: "{topic}".

Return ONLY a valid JSON array with no extra text, markdown, or explanation. Each object must have:
- "q": the question text (string)
- "opts": array of exactly 4 answer options (strings)
- "correct": index (0-3) of the correct option in opts
- "diff": one of "EASY", "MEDIUM", or "HARD"
- "hint": a short hint that guides without giving away the answer
- "explain": a clear explanation of why the correct answer is right

Mix difficulty: roughly 30% EASY, 50% MEDIUM, 20% HARD.
Make questions academically rigorous and unambiguous.
All 4 options must be plausible — no obviously wrong distractors.

Example format:
[{{"q":"What is...?","opts":["A","B","C","D"],"correct":2,"diff":"MEDIUM","hint":"Think about...","explain":"C is correct because..."}}]"""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system', 'content': 'You are a professional quiz creator. Output only valid JSON arrays, nothing else.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.7,
            max_tokens=4096,
        )
        raw = resp.choices[0].message.content.strip()

        # Strip markdown code fences if present
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        ai_questions = _json.loads(raw)

        # Validate and normalise
        questions = []
        for i, q in enumerate(ai_questions[:count]):
            opts = q.get('opts', [])
            correct = int(q.get('correct', 0))
            if len(opts) != 4 or correct not in range(4):
                continue
            questions.append({
                'id': i,
                'q': q.get('q', ''),
                'opts': opts,
                'correct': correct,
                'diff': q.get('diff', 'MEDIUM') + ' · +4/−1',
                'hint': q.get('hint', f'Think carefully about {topic}.'),
                'explain': q.get('explain', f'The correct answer is: {opts[correct]}'),
                'card_id': None,
            })

        if not questions:
            return JsonResponse({'error': 'AI returned no valid questions. Try again.'}, status=500)

        # Simple score prediction (rule-based since no flashcard history for AI questions)
        n = len(questions)
        easy = sum(1 for q in questions if 'EASY' in q['diff'])
        hard = sum(1 for q in questions if 'HARD' in q['diff'])
        avg_p_recall = (easy * 0.80 + hard * 0.45 + (n - easy - hard) * 0.62) / n
        predicted_score = max(0, round(avg_p_recall * n * 4 - (1 - avg_p_recall) * n))
        prediction = {
            'predicted_score': predicted_score,
            'predicted_accuracy': round(avg_p_recall * 100, 1),
            'max_score': n * 4,
            'confidence': 'medium',
        }

        return JsonResponse({'questions': questions, 'prediction': prediction, 'topic': topic})

    except _json.JSONDecodeError:
        return JsonResponse({'error': 'AI response could not be parsed. Please try again.'}, status=500)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@login_required
@require_http_methods(['GET'])
def generate_mock(request):
    """
    Generate a full-length mock test with mixed question types via Groq LLM.

    Query params:
        topic    (str)           — subject area
        count    (int, 20–50)    — total questions, default 30
        duration (int, minutes)  — test duration hint for instructions, default 60
    Response: {questions: [...], prediction: {...}, topic: str, duration: int}
    """
    import os, json as _json, re, math
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()

    topic = request.GET.get('topic', '').strip()
    if not topic:
        return JsonResponse({'error': 'topic required'}, status=400)
    try:
        duration = int(request.GET.get('duration', 60))
    except ValueError:
        duration = 60

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return JsonResponse({'error': 'Groq API key not configured'}, status=500)

    # Accept individual type counts (from stepper UI) or fall back to total-based split
    try:
        mcq_n  = min(int(request.GET.get('mcq',  -1)), 30)
        tf_n   = min(int(request.GET.get('tf',   -1)), 20)
        fitb_n = min(int(request.GET.get('fitb', -1)), 20)
        ar_n   = min(int(request.GET.get('ar',   -1)), 15)
    except ValueError:
        mcq_n = tf_n = fitb_n = ar_n = -1

    if mcq_n < 0 or tf_n < 0 or fitb_n < 0 or ar_n < 0:
        # Legacy fallback: distribute from total count
        try:
            count = min(max(int(request.GET.get('count', 30)), 10), 50)
        except ValueError:
            count = 30
        mcq_n   = math.ceil(count * 0.40)
        tf_n    = math.ceil(count * 0.25)
        fitb_n  = math.ceil(count * 0.20)
        ar_n    = count - mcq_n - tf_n - fitb_n

    count = mcq_n + tf_n + fitb_n + ar_n
    if count == 0:
        return JsonResponse({'error': 'Total question count cannot be zero.'}, status=400)

    prompt = f"""You are an expert exam setter. Create a rigorous full-length mock test on "{topic}".

Generate exactly {count} questions with this distribution:
- {mcq_n} MCQ (qtype "MCQ"): 4 answer options, all plausible, no trick questions
- {tf_n} True/False (qtype "TRUE_FALSE"): opts must be exactly ["True", "False"]
- {fitb_n} Fill in the Blank (qtype "FILL_BLANK"): question has a ___ gap; provide 4 options where only one correctly fills the gap
- {ar_n} Assertion-Reason (qtype "ASSERTION"): state Assertion (A) and Reason (R); opts must be exactly:
  ["Both A and R are true, and R correctly explains A",
   "Both A and R are true, but R does not explain A",
   "A is true but R is false",
   "A is false but R is true",
   "Both A and R are false"]

Return ONLY a valid JSON array — no markdown, no extra text.
Each element: {{"q":"...","opts":[...],"correct":0,"diff":"EASY|MEDIUM|HARD","hint":"...","explain":"...","qtype":"..."}}

Difficulty spread: 25% EASY, 50% MEDIUM, 25% HARD.
Questions must be academically rigorous, syllabus-level, and unambiguous."""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system', 'content': 'You are a professional exam setter. Output only valid JSON arrays, nothing else.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.65,
            max_tokens=8192,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        ai_questions = _json.loads(raw)

        questions = []
        for i, q in enumerate(ai_questions[:count]):
            opts = q.get('opts', [])
            correct = int(q.get('correct', 0))
            qtype = q.get('qtype', 'MCQ')
            if len(opts) < 2 or correct not in range(len(opts)):
                continue
            diff_raw = q.get('diff', 'MEDIUM')
            questions.append({
                'id': i,
                'q': q.get('q', ''),
                'opts': opts,
                'correct': correct,
                'diff': f"{qtype.replace('_',' ')} · {diff_raw} · +4/−1",
                'hint': q.get('hint', f'Think carefully about {topic}.'),
                'explain': q.get('explain', f'The correct answer is: {opts[correct]}'),
                'card_id': None,
                'qtype': qtype,
            })

        if not questions:
            return JsonResponse({'error': 'AI returned no valid questions. Try again.'}, status=500)

        n = len(questions)
        easy = sum(1 for q in questions if 'EASY' in q['diff'])
        hard = sum(1 for q in questions if 'HARD' in q['diff'])
        avg_p = (easy * 0.78 + hard * 0.42 + (n - easy - hard) * 0.60) / n
        predicted_score = max(0, round(avg_p * n * 4 - (1 - avg_p) * n))
        prediction = {
            'predicted_score': predicted_score,
            'predicted_accuracy': round(avg_p * 100, 1),
            'max_score': n * 4,
            'confidence': 'medium',
            'breakdown': {'MCQ': mcq_n, 'TRUE_FALSE': tf_n, 'FILL_BLANK': fitb_n, 'ASSERTION': ar_n},
        }
        return JsonResponse({'questions': questions, 'prediction': prediction, 'topic': topic, 'duration': duration})

    except _json.JSONDecodeError:
        return JsonResponse({'error': 'AI response could not be parsed. Please try again.'}, status=500)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@login_required
@require_http_methods(['GET'])
def video_search(request):
    """
    Return up to 6 curated YouTube video recommendations for a topic via Groq LLM.
    Each video ID is validated live via YouTube's oEmbed API — invalid/deleted videos
    are automatically replaced with YouTube search links.

    Query params: topic (str)
    Response: {videos: [{title, channel, youtube_id, description, duration, level, watch_url, thumbnail}], topic}
    """
    import os, json as _json, re, requests as _req
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from urllib.parse import quote
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()

    topic = request.GET.get('topic', '').strip()
    if not topic:
        return JsonResponse({'error': 'topic required'}, status=400)

    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return JsonResponse({'error': 'Groq API key not configured'}, status=500)

    def _validate_video(vid_id):
        """Return real thumbnail URL if video exists, else None."""
        try:
            r = _req.get(
                'https://www.youtube.com/oembed',
                params={'url': f'https://www.youtube.com/watch?v={vid_id}', 'format': 'json'},
                timeout=5,
            )
            if r.status_code == 200:
                return r.json().get('thumbnail_url')
        except Exception:
            pass
        return None

    prompt = f"""Recommend exactly 10 high-quality educational YouTube videos about "{topic}".

Mix languages: include at least 3 videos in Hindi and the rest in English.
Spread difficulty evenly — include at least 2 Beginner, 4 Intermediate, and 2 Advanced videos.

Return ONLY a valid JSON array — no markdown, no extra text. Each object must have:
- "title": exact video title (string)
- "channel": YouTube channel name (string)
- "youtube_id": the real 11-character YouTube video ID (string)
- "description": one clear sentence about what the video covers (string)
- "duration": approximate length like "14 min" or "1h 22m" (string)
- "level": one of "Beginner", "Intermediate", "Advanced" (string)
- "lang": "Hindi" or "English" (string)

English channels to prefer: Khan Academy, 3Blue1Brown, MIT OpenCourseWare, CrashCourse, Kurzgesagt, TED-Ed, freeCodeCamp, StatQuest, Veritasium, Sentdex, Computerphile, The Organic Chemistry Tutor, Physics Girl.
Hindi channels to prefer: Physics Wallah (PW), Khan Academy Hindi, Unacademy, Vedantu, MyClassroom, Apni Kaksha, Exam Fear, Learnohub, Study IQ.

Only include videos whose youtube_id you are highly confident is correct and the video is still available. The ID must be exactly 11 characters (letters, digits, - or _).

Example format:
[{{"title":"But what is a neural network?","channel":"3Blue1Brown","youtube_id":"aircAruvnKk","description":"A visual intro to neural networks.","duration":"19 min","level":"Beginner","lang":"English"}}]"""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[
                {'role': 'system', 'content': 'You are an educational video curator. Output only valid JSON arrays, nothing else.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        videos_raw = _json.loads(raw)

        # Build candidate list — filter obviously bad IDs first
        _level_order = {'Beginner': 0, 'Intermediate': 1, 'Advanced': 2}
        candidates = []
        for v in videos_raw[:10]:
            vid_id = str(v.get('youtube_id', '')).strip()
            valid  = bool(re.match(r'^[A-Za-z0-9_-]{11}$', vid_id))
            candidates.append({
                'title':       v.get('title', ''),
                'channel':     v.get('channel', ''),
                'youtube_id':  vid_id if valid else None,
                'description': v.get('description', ''),
                'duration':    v.get('duration', ''),
                'level':       v.get('level', 'Intermediate'),
                'lang':        v.get('lang', 'English'),
            })

        # Validate IDs in parallel via YouTube oEmbed (no API key required)
        id_futures = {}
        with ThreadPoolExecutor(max_workers=10) as pool:
            for i, c in enumerate(candidates):
                if c['youtube_id']:
                    id_futures[pool.submit(_validate_video, c['youtube_id'])] = i
            for fut in as_completed(id_futures):
                i = id_futures[fut]
                thumb = fut.result()
                candidates[i]['thumbnail'] = thumb      # None = video unavailable
                if not thumb:
                    candidates[i]['youtube_id'] = None  # Mark as invalid

        # Build final list with watch/search URLs
        videos = []
        for c in candidates:
            search_q = quote(f"{c['title']} {c['channel']}")
            if c.get('youtube_id') and c.get('thumbnail'):
                c['watch_url'] = f"https://www.youtube.com/watch?v={c['youtube_id']}"
            else:
                c['thumbnail'] = None
                c['watch_url'] = f"https://www.youtube.com/results?search_query={search_q}"
                c['youtube_id'] = None
            videos.append(c)

        # Sort: validated first, then by level (Beginner → Intermediate → Advanced)
        videos.sort(key=lambda x: (
            0 if x['thumbnail'] else 1,
            _level_order.get(x['level'], 1),
        ))
        videos = videos[:9]  # up to 9: 3 per level row

        if not videos:
            return JsonResponse({'error': 'No video recommendations found. Try a different topic.'}, status=500)

        return JsonResponse({'videos': videos, 'topic': topic})

    except _json.JSONDecodeError:
        return JsonResponse({'error': 'Could not parse AI response. Please try again.'}, status=500)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)


@login_required
@require_http_methods(['GET'])
def study_time(request):
    """
    Return the user's computed peak study-focus window.

    GET /api/analytics/study-time/
    → 200 {peak_window, peak_days, heatmap, message, confidence, productivity_score}
    → 200 {status: "warming_up", message: "..."} when data is insufficient
    """
    from analytics.ml.study_time import get_recommendation
    try:
        result = get_recommendation(request.user.id)
        return JsonResponse(result)
    except Exception as exc:
        return JsonResponse({'status': 'warming_up', 'message': str(exc)})
