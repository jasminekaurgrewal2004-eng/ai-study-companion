from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
from .models import JournalEntry, ChatHistory, ChatSession, Syllabus, SyllabusItem, Flashcard, FlashcardReview, QuizAttempt, StudyPlan, StudyPlanTask, Reminder
from .ml_services import ForgettingCurvePredictor, ConfusionTopicAnalyzer, PerformanceRiskScorer
from groq import Groq
import os
from dotenv import load_dotenv
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

load_dotenv()

# Configure Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@login_required
def dashboard(request):
    ctx = {
        'vid_topic_chips': [
            'Machine Learning', 'Calculus', 'Organic Chemistry',
            'Python Programming', 'World History', 'Electromagnetism',
            'Data Structures', 'Cell Biology', 'Linear Algebra', 'Thermodynamics',
        ],
        'st_hour_labels': ['0h','3h','6h','9h','12h','15h','18h','21h'],
    }
    return render(request, 'core/dashboard.html', ctx)

def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/login.html')

@csrf_exempt
def api_signup(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            
            if User.objects.filter(username=username).exists():
                return JsonResponse({'msg': 'Username already exists'}, status=400)
            
            if User.objects.filter(email=email).exists():
                return JsonResponse({'msg': 'Email already registered'}, status=400)
            
            user = User.objects.create_user(username=username, email=email, password=password)
            return JsonResponse({'msg': 'User created successfully', 'user': {'username': user.username}})
        except Exception as e:
            return JsonResponse({'msg': str(e)}, status=400)
    return JsonResponse({'msg': 'Method not allowed'}, status=405)

@csrf_exempt
def api_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            identifier = data.get('email', '').strip()
            password = data.get('password', '')
            print(f"DEBUG: Login attempt for identifier: '{identifier}' (length: {len(identifier)})")
            print(f"DEBUG: Password length: {len(password)}")
            
            # Check if identifier is email or username
            user_obj = User.objects.filter(email__iexact=identifier).first()
            if not user_obj:
                user_obj = User.objects.filter(username__iexact=identifier).first()
                
            if not user_obj:
                print(f"DEBUG: User not found for '{identifier}'")
                return JsonResponse({'msg': 'Invalid credentials'}, status=400)
            
            username = user_obj.username
            print(f"DEBUG: Found user {username}, authenticating...")
            user = authenticate(username=username, password=password)
            if user:
                print(f"DEBUG: User authenticated: {username}")
                auth_login(request, user)
                return JsonResponse({
                    'msg': 'Login successful',
                    'token': 'dummy-session-token',
                    'user': {
                        'username': user.username,
                        'email': user.email,
                        'plan': 'Free'
                    }
                })
            else:
                print(f"DEBUG: Authentication failed for {username}")
                return JsonResponse({'msg': 'Invalid credentials'}, status=400)
        except Exception as e:
            return JsonResponse({'msg': str(e)}, status=400)
    return JsonResponse({'msg': 'Method not allowed'}, status=405)

def api_logout(request):
    auth_logout(request)
    return redirect('login')

@login_required
@csrf_exempt
def api_journals(request):
    print(f"DEBUG: api_journals called. Method: {request.method}, User: {request.user}")
    if request.method == 'GET':
        journals = JournalEntry.objects.filter(user=request.user)
        data = [{
            'id': j.id, 
            'title': j.title, 
            'content': j.content, 
            'date': j.date, 
            'mood': j.mood,
            'is_protected': j.is_protected
        } for j in journals]
        return JsonResponse(data, safe=False)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(f"DEBUG: Creating journal for {request.user}: {data.get('title')}")
            journal = JournalEntry.objects.create(
                user=request.user,
                title=data.get('title'),
                content=data.get('content'),
                mood=data.get('mood'),
                is_protected=data.get('is_protected', False),
                entry_password=data.get('entry_password', '')
            )
            print(f"DEBUG: Journal created with ID {journal.id}")
            return JsonResponse({'id': journal.id, 'msg': 'Journal created'})
        except Exception as e:
            print(f"DEBUG ERROR: {str(e)}")
            return JsonResponse({'msg': str(e)}, status=400)
    
    return JsonResponse({'msg': 'Method not allowed'}, status=405)

@login_required
@csrf_exempt
def api_journal_detail(request, pk):
    print(f"DEBUG: api_journal_detail called for ID {pk}. Method: {request.method}")
    journal = get_object_or_404(JournalEntry, pk=pk, user=request.user)
    
    if request.method == 'GET':
        return JsonResponse({
            'id': journal.id,
            'title': journal.title,
            'content': journal.content,
            'is_protected': journal.is_protected,
            'mood': journal.mood,
            'entry_password': journal.entry_password
        })

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            print(f"DEBUG: Updating journal {pk}: {data}")
            journal.title = data.get('title', journal.title)
            journal.content = data.get('content', journal.content)
            journal.mood = data.get('mood', journal.mood)
            journal.is_protected = data.get('is_protected', journal.is_protected)
            journal.entry_password = data.get('entry_password', journal.entry_password)
            journal.save()
            return JsonResponse({'msg': 'Journal updated'})
        except Exception as e:
            print(f"DEBUG ERROR: {str(e)}")
            return JsonResponse({'msg': str(e)}, status=400)
            
    if request.method == 'DELETE':
        journal.delete()
        print(f"DEBUG: Journal {pk} deleted")
        return JsonResponse({'msg': 'Journal deleted'})
        
    return JsonResponse({'msg': 'Method not allowed'}, status=405)

@login_required
@csrf_exempt
def api_chat_sessions(request):
    if request.method == 'GET':
        from django.db.models import Count
        sessions = (
            ChatSession.objects
            .filter(user=request.user)
            .annotate(msg_count=Count('messages'))
            .filter(msg_count__gt=0)
            .order_by('-updated_at')
        )
        data = [{'id': s.id, 'title': s.title, 'updated_at': s.updated_at.isoformat()} for s in sessions]
        return JsonResponse(data, safe=False)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_chat_session_detail(request, pk):
    session = get_object_or_404(ChatSession, pk=pk, user=request.user)

    if request.method == 'DELETE':
        session.delete()
        return JsonResponse({'msg': 'Session deleted'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_chat(request):
    if request.method == 'GET':
        session_id = request.GET.get('session_id')
        if session_id:
            messages = ChatHistory.objects.filter(user=request.user, session_id=session_id).order_by('timestamp')
        else:
            session = ChatSession.objects.filter(user=request.user).first()
            messages = ChatHistory.objects.filter(session=session).order_by('timestamp') if session else ChatHistory.objects.none()
        data = [{'role': m.role, 'content': m.content, 'timestamp': m.timestamp.isoformat()} for m in messages]
        return JsonResponse(data, safe=False)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message')
            history = data.get('history', [])
            session_id = data.get('session_id')

            if not user_message:
                return JsonResponse({'error': 'No message provided'}, status=400)

            # Get or create session
            session = None
            if session_id:
                session = ChatSession.objects.filter(id=session_id, user=request.user).first()
            if not session:
                session = ChatSession.objects.create(user=request.user, title='New Conversation')

            # Save user message
            ChatHistory.objects.create(user=request.user, session=session, role='user', content=user_message)

            # Set session title from first user message
            if session.title == 'New Conversation':
                session.title = user_message[:80].strip()
                session.save()

            # Prepare messages for Groq
            messages = [
                {"role": "system", "content": "You are Sage, a world-class AI learning assistant inside the AI Study Companion app. You help people across every domain — students, professionals, researchers, developers, creatives, and lifelong learners. You adapt your language, depth, and examples to the user's domain and level. Always be helpful, clear, and concise."}
            ]
            for h in history:
                role = "assistant" if h.get('role') == 'assistant' else "user"
                content = h.get('content', '')
                if content:
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_message})

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return JsonResponse({'error': 'Groq API key is missing. Please check your .env file.'}, status=500)

            local_client = Groq(api_key=api_key)
            chat_completion = local_client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
            )
            bot_reply = chat_completion.choices[0].message.content

            # Save bot message
            ChatHistory.objects.create(user=request.user, session=session, role='assistant', content=bot_reply)

            return JsonResponse({'text': bot_reply, 'session_id': session.id, 'session_title': session.title})
        except Exception as e:
            print(f"CHAT API ERROR: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# =================== SYLLABUS API ===================

@login_required
@csrf_exempt
def api_syllabi(request):
    """List all syllabi or create a new one."""
    if request.method == 'GET':
        syllabi = Syllabus.objects.filter(user=request.user)
        data = []
        for s in syllabi:
            items = s.items.all()
            item_count = items.count()
            text_count = items.filter(item_type='text').count()
            image_count = items.filter(item_type='image').count()
            file_count = items.filter(item_type='file').count()
            data.append({
                'id': s.id,
                'title': s.title,
                'subject': s.subject,
                'description': s.description,
                'item_count': item_count,
                'text_count': text_count,
                'image_count': image_count,
                'file_count': file_count,
                'created_at': s.created_at.isoformat(),
                'updated_at': s.updated_at.isoformat(),
            })
        return JsonResponse(data, safe=False)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            syllabus = Syllabus.objects.create(
                user=request.user,
                title=data.get('title', 'Untitled Syllabus'),
                subject=data.get('subject', ''),
                description=data.get('description', ''),
            )
            return JsonResponse({'id': syllabus.id, 'msg': 'Syllabus created'})
        except Exception as e:
            return JsonResponse({'msg': str(e)}, status=400)

    return JsonResponse({'msg': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_syllabus_detail(request, pk):
    """Get, update, or delete a single syllabus with all its items."""
    syllabus = get_object_or_404(Syllabus, pk=pk, user=request.user)

    if request.method == 'GET':
        items = syllabus.items.all()
        items_data = []
        for item in items:
            item_data = {
                'id': item.id,
                'item_type': item.item_type,
                'content': item.content,
                'file_name': item.file_name,
                'order': item.order,
                'created_at': item.created_at.isoformat(),
            }
            if item.image:
                item_data['image_url'] = item.image.url
            if item.file:
                item_data['file_url'] = item.file.url
                item_data['file_name'] = item.file_name
                item_data['file_size'] = item.file_size
                item_data['file_type'] = item.file_type
            items_data.append(item_data)
        return JsonResponse({
            'id': syllabus.id,
            'title': syllabus.title,
            'subject': syllabus.subject,
            'description': syllabus.description,
            'items': items_data,
            'created_at': syllabus.created_at.isoformat(),
            'updated_at': syllabus.updated_at.isoformat(),
        })

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            syllabus.title = data.get('title', syllabus.title)
            syllabus.subject = data.get('subject', syllabus.subject)
            syllabus.description = data.get('description', syllabus.description)
            syllabus.save()
            return JsonResponse({'msg': 'Syllabus updated'})
        except Exception as e:
            return JsonResponse({'msg': str(e)}, status=400)

    if request.method == 'DELETE':
        syllabus.delete()
        return JsonResponse({'msg': 'Syllabus deleted'})

    return JsonResponse({'msg': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_syllabus_add_item(request, pk):
    """Add a text note, image, or any file to a syllabus."""
    syllabus = get_object_or_404(Syllabus, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            item_type = request.POST.get('item_type', 'text')
            content = request.POST.get('content', '')
            order = syllabus.items.count()

            # Handle image uploads
            if item_type == 'image' and 'image' in request.FILES:
                item = SyllabusItem.objects.create(
                    syllabus=syllabus,
                    item_type='image',
                    content=content,
                    image=request.FILES['image'],
                    order=order,
                )
                return JsonResponse({
                    'id': item.id,
                    'item_type': item.item_type,
                    'content': item.content,
                    'image_url': item.image.url,
                    'order': item.order,
                    'msg': 'Image added'
                })

            # Handle link items
            elif item_type == 'link':
                url = request.POST.get('content', '').strip()
                title = request.POST.get('file_name', '').strip()
                if not url:
                    return JsonResponse({'msg': 'URL is required'}, status=400)
                item = SyllabusItem.objects.create(
                    syllabus=syllabus,
                    item_type='link',
                    content=url,
                    file_name=title,
                    order=order,
                )
                return JsonResponse({
                    'id': item.id,
                    'item_type': 'link',
                    'content': item.content,
                    'file_name': item.file_name,
                    'order': item.order,
                    'msg': 'Link added'
                })

            # Handle generic file uploads (PDF, DOC, audio, video, etc.)
            elif item_type in ('file', 'pdf', 'audio', 'video') and 'file' in request.FILES:
                uploaded = request.FILES['file']
                item = SyllabusItem.objects.create(
                    syllabus=syllabus,
                    item_type=item_type,
                    content=content,
                    file=uploaded,
                    file_name=uploaded.name,
                    file_size=uploaded.size,
                    file_type=uploaded.content_type or '',
                    order=order,
                )
                return JsonResponse({
                    'id': item.id,
                    'item_type': item.item_type,
                    'content': item.content,
                    'file_url': item.file.url,
                    'file_name': item.file_name,
                    'file_size': item.file_size,
                    'file_type': item.file_type,
                    'order': item.order,
                    'msg': 'File uploaded'
                })

            # Handle text notes
            else:
                if not content:
                    try:
                        body_data = json.loads(request.body)
                        content = body_data.get('content', '')
                        item_type = body_data.get('item_type', 'text')
                    except:
                        pass

                item = SyllabusItem.objects.create(
                    syllabus=syllabus,
                    item_type='text',
                    content=content,
                    order=order,
                )
                return JsonResponse({
                    'id': item.id,
                    'item_type': item.item_type,
                    'content': item.content,
                    'order': item.order,
                    'msg': 'Note added'
                })
        except Exception as e:
            print(f"SYLLABUS ITEM ERROR: {str(e)}")
            return JsonResponse({'msg': str(e)}, status=400)

    return JsonResponse({'msg': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_syllabus_delete_item(request, pk, item_id):
    """Delete a specific item from a syllabus."""
    syllabus = get_object_or_404(Syllabus, pk=pk, user=request.user)
    item = get_object_or_404(SyllabusItem, pk=item_id, syllabus=syllabus)

    if request.method == 'DELETE':
        item.delete()
        return JsonResponse({'msg': 'Item deleted'})

    return JsonResponse({'msg': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_syllabus_insights(request, pk):
    """Generate AI-powered study plan and insights from syllabus content."""
    syllabus = get_object_or_404(Syllabus, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            items = syllabus.items.all()
            all_text = []
            for item in items:
                if item.item_type == 'text' and item.content:
                    all_text.append(item.content)

                elif item.item_type == 'image' and item.content:
                    all_text.append(f"[Image caption: {item.content}]")

                elif item.item_type in ('file', 'pdf') and item.file:
                    # Try to extract text from PDF
                    if HAS_PYPDF2 and (item.file_type == 'application/pdf' or item.file_name.lower().endswith('.pdf')):
                        try:
                            item.file.seek(0)
                            reader = PyPDF2.PdfReader(item.file)
                            pages_text = []
                            for page in reader.pages[:20]:  # cap at 20 pages
                                pages_text.append(page.extract_text() or '')
                            extracted = '\n'.join(pages_text).strip()
                            if extracted:
                                all_text.append(f"[PDF: {item.file_name}]\n{extracted}")
                            else:
                                all_text.append(f"[PDF uploaded: {item.file_name} — text could not be extracted]")
                        except Exception:
                            all_text.append(f"[PDF uploaded: {item.file_name}]")
                    else:
                        desc = item.content or ''
                        all_text.append(f"[File uploaded: {item.file_name}{' — ' + desc if desc else ''}]")

                elif item.item_type == 'audio':
                    desc = item.content or ''
                    all_text.append(f"[Audio file: {item.file_name}{' — ' + desc if desc else ''}]")

                elif item.item_type == 'video':
                    desc = item.content or ''
                    all_text.append(f"[Video file: {item.file_name}{' — ' + desc if desc else ''}]")

                elif item.item_type == 'link':
                    title = item.file_name or ''
                    all_text.append(f"[Resource link: {title + ' — ' if title else ''}{item.content}]")

            if not all_text:
                return JsonResponse({
                    'error': 'No content found in this syllabus. Add some notes, files, or links first!'
                }, status=400)

            combined_content = "\n\n".join(all_text)

            prompt = f"""You are Sage, an AI learning assistant. Someone uploaded material for **"{syllabus.title}"** (Domain/Subject: {syllabus.subject or 'General'}).

Material:
---
{combined_content[:4000]}
---

Create a learning plan using the EXACT format below. Rules:
- Use ## for every section heading (with the emoji shown)
- Every point is a single short bullet (- )
- **Bold** the key word or concept in each bullet
- No paragraphs, no long sentences, max 10 words per bullet
- Be specific to the actual material above — adapt tone to the domain (academic, professional, technical, creative, etc.)

## 📋 What's Covered
- **[topic/concept]** — one phrase
(3–5 bullets)

## 🎯 Key Areas to Focus On
- 🔴 **[topic]** — why it's critical
- 🟡 **[topic]** — why it's important
- 🟢 **[topic]** — good to know
(list all major areas with a priority label)

## 📅 7-Day Learning Plan
- **Day 1:** [specific topic from material]
- **Day 2:** [specific topic]
- **Day 3:** [specific topic]
- **Day 4:** [specific topic]
- **Day 5:** [specific topic]
- **Day 6:** [specific topic]
- **Day 7:** Review everything + apply / practice

## 💡 Learning Tips
- **[tip name]:** one-line advice specific to this domain
(3–4 tips)

## ⚠️ Common Mistakes
- **[mistake]:** why people get it wrong
(3 mistakes, one line each)

## 🧠 Must-Know Points
- **[concept/fact]:** short explanation
(5–7 of the most important points)"""

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return JsonResponse({'error': 'Groq API key is missing.'}, status=500)

            local_client = Groq(api_key=api_key)
            chat_completion = local_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are Sage, an AI learning assistant for AI Study Companion. You help people from any domain — students, professionals, researchers, or anyone learning something new. Always respond with short bullet points only — never write long paragraphs. Keep every point to one line. Be clear, simple, and easy to read."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
            )
            insights = chat_completion.choices[0].message.content
            return JsonResponse({'insights': insights})

        except Exception as e:
            print(f"SYLLABUS INSIGHTS ERROR: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_syllabus_plan_chat(request, pk):
    """Chat with AI to customise the generated study plan."""
    syllabus = get_object_or_404(Syllabus, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            plan_context = data.get('plan', '')
            history = data.get('history', [])

            if not user_message:
                return JsonResponse({'error': 'Message is required'}, status=400)

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return JsonResponse({'error': 'Groq API key is missing.'}, status=500)

            system_prompt = (
                f'You are Sage, an AI learning assistant helping someone customise their learning plan '
                f'for "{syllabus.title}" (Domain/Subject: {syllabus.subject or "General"}).\n\n'
                f'The current plan is:\n---\n{plan_context[:3000]}\n---\n\n'
                'STRICT FORMAT RULES — follow these for EVERY response, no exceptions:\n'
                '- ALWAYS respond using bullet points (- ) only. Never write paragraphs or prose.\n'
                '- Every single point must be on its own bullet line starting with "- ".\n'
                '- **Bold** the key word or concept at the start of each bullet.\n'
                '- Keep each bullet to one short line (max 12 words).\n'
                '- If updating the plan, use ## headings + bullets matching the plan format.\n'
                '- If answering a question, still answer entirely in bullets — no sentences, no paragraphs.\n'
                '- Never write introductory sentences like "Here is..." or "Sure!" — go straight to bullets.\n'
                '- Maximum 10 bullets per response unless the user asks for a full plan section.'
            )

            messages = [{"role": "system", "content": system_prompt}]
            for h in history[-10:]:  # keep last 10 turns for context
                if h.get('role') in ('user', 'assistant') and h.get('content'):
                    messages.append({"role": h['role'], "content": h['content']})
            messages.append({"role": "user", "content": user_message})

            local_client = Groq(api_key=api_key)
            completion = local_client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
            )
            reply = completion.choices[0].message.content
            return JsonResponse({'reply': reply})

        except Exception as e:
            print(f"PLAN CHAT ERROR: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_syllabus_monthly_plan(request, pk):
    """Generate a month-by-month, day-by-day study plan from syllabus content."""
    syllabus = get_object_or_404(Syllabus, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            months = max(1, min(int(data.get('months', 2)), 6))

            items = syllabus.items.all()
            all_text = []
            for item in items:
                if item.item_type == 'text' and item.content:
                    all_text.append(item.content)
                elif item.item_type == 'image' and item.content:
                    all_text.append(f"[Image caption: {item.content}]")
                elif item.item_type in ('file', 'pdf') and item.file:
                    if HAS_PYPDF2 and (item.file_type == 'application/pdf' or item.file_name.lower().endswith('.pdf')):
                        try:
                            item.file.seek(0)
                            reader = PyPDF2.PdfReader(item.file)
                            pages_text = [page.extract_text() or '' for page in reader.pages[:20]]
                            extracted = '\n'.join(pages_text).strip()
                            all_text.append(f"[PDF: {item.file_name}]\n{extracted}" if extracted else f"[PDF: {item.file_name}]")
                        except Exception:
                            all_text.append(f"[PDF: {item.file_name}]")
                    else:
                        all_text.append(f"[File: {item.file_name}]")
                elif item.item_type == 'audio':
                    all_text.append(f"[Audio: {item.file_name}]")
                elif item.item_type == 'video':
                    all_text.append(f"[Video: {item.file_name}]")
                elif item.item_type == 'link':
                    title = item.file_name or ''
                    all_text.append(f"[Resource: {title + ' — ' if title else ''}{item.content}]")

            if not all_text:
                return JsonResponse({'error': 'No content found. Add notes, files, or links first!'}, status=400)

            combined_content = "\n\n".join(all_text)

            prompt = f"""You are Sage, an AI learning assistant. Create a detailed {months}-month study plan for **"{syllabus.title}"** (Subject: {syllabus.subject or 'General'}).

Material:
---
{combined_content[:4000]}
---

Generate a complete month-by-month, day-by-day study plan using EXACTLY the format below.

STRICT FORMAT RULES:
- Use ## for each Month heading
- Use ### for each Week heading inside a month
- Every day is ONE bullet line: - **Day N (Weekday):** short specific task
- Max 10 words per day entry
- Days 6 & 7 are always lighter (review / rest)
- Be specific to the actual material above
- Cover ALL {months} months with 4 weeks each and all 7 days

## 📅 Month 1 — [Theme: what the student masters this month]
### Week 1: [Week focus]
- **Day 1 (Mon):** [specific topic from material]
- **Day 2 (Tue):** [specific topic]
- **Day 3 (Wed):** [specific topic]
- **Day 4 (Thu):** [specific topic]
- **Day 5 (Fri):** [specific topic] + quick practice
- **Day 6 (Sat):** Review Week 1 highlights
- **Day 7 (Sun):** Light revision / rest

### Week 2: [Week focus]
(7 days same format)

### Week 3: [Week focus]
(7 days same format)

### Week 4: [Week focus]
(7 days — Day 28: Month 1 recap & self-test)

## 📅 Month 2 — [Theme]
(same 4-week, 7-day structure)

Repeat for all {months} months. Every day must have a real task."""

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return JsonResponse({'error': 'Groq API key is missing.'}, status=500)

            local_client = Groq(api_key=api_key)
            chat_completion = local_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Sage, an AI learning assistant. Generate detailed month-by-month, "
                            "day-by-day study plans. Always use ## for months, ### for weeks, and bullet "
                            "points for each day. Never write paragraphs. Be specific to the material. "
                            "Every day must have a clear, actionable one-line task."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                max_tokens=4096,
            )
            plan = chat_completion.choices[0].message.content
            return JsonResponse({'plan': plan})

        except Exception as e:
            print(f"MONTHLY PLAN ERROR: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_syllabus_monthly_plan_chat(request, pk):
    """Chat with AI to customise the generated monthly study plan."""
    syllabus = get_object_or_404(Syllabus, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            plan_context = data.get('plan', '')
            history = data.get('history', [])

            if not user_message:
                return JsonResponse({'error': 'Message is required'}, status=400)

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return JsonResponse({'error': 'Groq API key is missing.'}, status=500)

            system_prompt = (
                f'You are Sage, an AI learning assistant helping someone customise their monthly study plan '
                f'for "{syllabus.title}" (Domain/Subject: {syllabus.subject or "General"}).\n\n'
                f'The current monthly plan is:\n---\n{plan_context[:3000]}\n---\n\n'
                'STRICT FORMAT RULES — follow these for EVERY response, no exceptions:\n'
                '- ALWAYS respond using bullet points (- ) only. Never write paragraphs or prose.\n'
                '- When updating the plan, keep the structure: ## Month, ### Week, bullets for each day.\n'
                '- Day format must stay: - **Day N (Weekday):** short specific task\n'
                '- Each bullet is one line, max 12 words.\n'
                '- If changing a month or week, respond with only that updated section — not the whole plan.\n'
                '- If answering a question, answer in bullets only — no intro sentences.\n'
                '- Never start with "Sure!", "Here is...", or any filler — go straight to content.\n'
            )

            messages = [{"role": "system", "content": system_prompt}]
            for h in history[-10:]:
                if h.get('role') in ('user', 'assistant') and h.get('content'):
                    messages.append({"role": h['role'], "content": h['content']})
            messages.append({"role": "user", "content": user_message})

            local_client = Groq(api_key=api_key)
            completion = local_client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
            )
            reply = completion.choices[0].message.content
            return JsonResponse({'reply': reply})

        except Exception as e:
            print(f"MONTHLY PLAN CHAT ERROR: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# =================== FLASHCARD API ===================

@login_required
def api_flashcard_subjects(request):
    """Return distinct flashcard subjects for the logged-in user with card counts."""
    from django.db.models import Count
    subjects = (
        Flashcard.objects.filter(user=request.user)
        .values('subject')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    return JsonResponse({'subjects': list(subjects)})


@login_required
@csrf_exempt
def api_flashcards(request):
    if request.method == 'GET':
        subject = request.GET.get('subject', '')
        qs = Flashcard.objects.filter(user=request.user).order_by('-created_at')
        if subject:
            qs = qs.filter(subject__iexact=subject)
        now = timezone.now()
        data = [{
            'id': c.id, 'front': c.front, 'back': c.back, 'subject': c.subject,
            'interval': c.interval, 'repetitions': c.repetitions,
            'ease_factor': round(c.ease_factor, 2),
            'next_review': c.next_review.isoformat(),
            'is_due': c.next_review <= now,
            'created_at': c.created_at.isoformat(),
        } for c in qs]
        return JsonResponse(data, safe=False)

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            front = body.get('front', '').strip()
            back = body.get('back', '').strip()
            if not front or not back:
                return JsonResponse({'error': 'front and back are required'}, status=400)
            card = Flashcard.objects.create(
                user=request.user,
                front=front,
                back=back,
                subject=body.get('subject', 'General').strip(),
            )
            return JsonResponse({'id': card.id, 'msg': 'Flashcard created'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_generate_flashcards(request):
    """Use AI to generate flashcards on any topic."""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            topic = body.get('topic', '').strip()
            count = min(max(int(body.get('count', 10)), 1), 30)
            difficulty = body.get('difficulty', 'mixed').strip()

            if not topic:
                return JsonResponse({'error': 'Topic is required'}, status=400)

            api_key = os.getenv('GROQ_API_KEY')
            if not api_key:
                return JsonResponse({'error': 'Groq API key is missing.'}, status=500)

            prompt = (
                f'Generate exactly {count} flashcards about "{topic}".\n'
                f'Difficulty level: {difficulty} (easy = definitions and basics, '
                f'medium = application and understanding, hard = advanced and tricky, '
                f'mixed = a variety).\n\n'
                'IMPORTANT: Respond ONLY with a valid JSON array. No markdown, no explanation, no code fences.\n'
                'Each object must have exactly two keys: "front" (the question) and "back" (the answer).\n\n'
                'Rules:\n'
                '- front: clear, concise question or concept (max 30 words)\n'
                '- back: accurate, helpful answer (max 60 words)\n'
                '- Cover different aspects of the topic\n'
                '- Make them genuinely educational and useful for studying\n'
                '- Include a mix of conceptual, factual, and application-based questions\n\n'
                'Example format:\n'
                '[{"front":"What is X?","back":"X is..."},{"front":"How does Y work?","back":"Y works by..."}]'
            )

            local_client = Groq(api_key=api_key)
            completion = local_client.chat.completions.create(
                messages=[
                    {'role': 'system', 'content': 'You are a flashcard generator. You ONLY respond with a valid JSON array of flashcard objects. Never include markdown formatting, code fences, or explanations. Just the raw JSON array.'},
                    {'role': 'user', 'content': prompt}
                ],
                model='llama-3.3-70b-versatile',
                temperature=0.7,
            )
            raw = completion.choices[0].message.content.strip()

            # Clean up response - strip markdown code fences if present
            if raw.startswith('```'):
                code_lines = raw.split('\n')
                raw = '\n'.join(code_lines[1:])
                if raw.endswith('```'):
                    raw = raw[:-3].strip()

            cards_data = json.loads(raw)
            if not isinstance(cards_data, list):
                return JsonResponse({'error': 'AI returned unexpected format. Please try again.'}, status=400)

            subject = topic.strip().title()

            created = []
            for item in cards_data:
                front = (item.get('front') or '').strip()
                back = (item.get('back') or '').strip()
                if not front or not back:
                    continue
                card = Flashcard.objects.create(
                    user=request.user,
                    front=front,
                    back=back,
                    subject=subject,
                )
                created.append({
                    'id': card.id,
                    'front': card.front,
                    'back': card.back,
                    'subject': card.subject,
                })

            return JsonResponse({
                'msg': f'{len(created)} flashcards created for "{topic}"',
                'count': len(created),
                'cards': created,
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'AI response could not be parsed. Please try again.'}, status=400)
        except Exception as e:
            print(f'GENERATE FLASHCARDS ERROR: {str(e)}')
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_flashcard_detail(request, pk):
    card = get_object_or_404(Flashcard, pk=pk, user=request.user)

    if request.method == 'GET':
        now = timezone.now()
        points = ForgettingCurvePredictor.forgetting_curve_points(card)
        return JsonResponse({
            'id': card.id, 'front': card.front, 'back': card.back,
            'subject': card.subject, 'interval': card.interval,
            'repetitions': card.repetitions, 'ease_factor': round(card.ease_factor, 2),
            'next_review': card.next_review.isoformat(),
            'is_due': card.next_review <= now,
            'forgetting_curve': points,
        })

    if request.method == 'DELETE':
        card.delete()
        return JsonResponse({'msg': 'Card deleted'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_flashcard_review(request, pk):
    """Record a review grade (0-5) and update SM-2 state."""
    card = get_object_or_404(Flashcard, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            grade = int(body.get('grade', 3))
            if not 0 <= grade <= 5:
                return JsonResponse({'error': 'grade must be 0-5'}, status=400)

            last_review = FlashcardReview.objects.filter(flashcard=card).order_by('-reviewed_at').first()
            if last_review:
                days_since = (timezone.now() - last_review.reviewed_at).total_seconds() / 86400
            else:
                days_since = 0.0

            FlashcardReview.objects.create(
                flashcard=card, user=request.user,
                grade=grade, days_since_last=round(days_since, 2),
            )

            updated = ForgettingCurvePredictor.sm2_update(card, grade)
            updated.save()

            return JsonResponse({
                'msg': 'Review recorded',
                'new_interval': updated.interval,
                'next_review': updated.next_review.isoformat(),
                'ease_factor': round(updated.ease_factor, 2),
                'repetitions': updated.repetitions,
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


# =================== DS INSIGHTS API ===================

@login_required
def api_predict_recall(request):
    """Return due cards with recall probabilities + deck summary."""
    if request.method == 'GET':
        try:
            due_cards = ForgettingCurvePredictor.get_due_cards(request.user)
            summary = ForgettingCurvePredictor.deck_summary(request.user)
            return JsonResponse({'due_cards': due_cards, 'summary': summary})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_confusion_map(request):
    """Return top confusion topics derived from chat history."""
    if request.method == 'GET':
        try:
            result = ConfusionTopicAnalyzer.analyze(request.user)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def api_risk_score(request):
    """Return a performance risk score with contributing factors."""
    if request.method == 'GET':
        try:
            result = PerformanceRiskScorer.score(request.user)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_quiz_attempt(request):
    """Record a quiz attempt for performance tracking."""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            attempt = QuizAttempt.objects.create(
                user=request.user,
                subject=body.get('subject', 'General'),
                score=float(body.get('score', 0)),
                total_questions=int(body.get('total_questions', 10)),
                correct_answers=int(body.get('correct_answers', 0)),
                time_taken_seconds=int(body.get('time_taken_seconds', 0)),
            )
            return JsonResponse({'id': attempt.id, 'msg': 'Quiz attempt recorded'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ─── Study Plan API ──────────────────────────────────────────────────────────

def _serialize_plan(plan):
    weeks = {}
    for task in plan.tasks.all():
        wk = task.week_number
        if wk not in weeks:
            weeks[wk] = {'week': wk, 'theme': task.week_theme, 'tasks': []}
        weeks[wk]['tasks'].append({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'is_completed': task.is_completed,
            'scheduled_date': str(task.scheduled_date) if task.scheduled_date else None,
        })
    total = plan.tasks.count()
    done = plan.tasks.filter(is_completed=True).count()
    first_dated = plan.tasks.filter(scheduled_date__isnull=False).order_by('scheduled_date').first()
    return {
        'id': plan.id,
        'subject': plan.subject,
        'goal': plan.goal,
        'duration_weeks': plan.duration_weeks,
        'hours_per_day': plan.hours_per_day,
        'created_at': plan.created_at.strftime('%b %d, %Y'),
        'total_tasks': total,
        'completed_tasks': done,
        'progress_pct': round(done / total * 100) if total else 0,
        'weeks': [weeks[k] for k in sorted(weeks)],
        'schedule_start': str(first_dated.scheduled_date) if first_dated else None,
    }


@login_required
@csrf_exempt
def api_study_plan(request):
    if request.method == 'GET':
        plan = StudyPlan.objects.filter(user=request.user, is_active=True).first()
        if not plan:
            return JsonResponse({'plan': None})
        return JsonResponse({'plan': _serialize_plan(plan)})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_study_plan_generate(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        body = json.loads(request.body)
        subject = body.get('subject', '').strip()
        goal = body.get('goal', '').strip()
        duration_weeks = max(1, min(12, int(body.get('duration_weeks', 4))))
        hours_per_day = max(0.5, min(10, float(body.get('hours_per_day', 2))))

        if not subject:
            return JsonResponse({'error': 'Subject is required'}, status=400)

        prompt = f"""Generate a structured {duration_weeks}-week study plan for: {subject}
Goal: {goal or 'Master the subject thoroughly'}
Daily commitment: {hours_per_day} hours per day

Return ONLY valid JSON in this exact format with no extra text:
{{
  "weeks": [
    {{
      "week": 1,
      "theme": "Short descriptive theme (e.g. Foundation & Basics)",
      "tasks": [
        {{"title": "Specific task title", "description": "1–2 sentence actionable description"}},
        {{"title": "...", "description": "..."}}
      ]
    }}
  ]
}}

Rules:
- Each week must have exactly 4 tasks
- Weeks must be numbered 1 through {duration_weeks}
- Tasks should be specific, actionable study activities
- Progress naturally from foundation to advanced topics
- Do NOT include markdown, code fences, or any text outside the JSON"""

        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()

        # Strip markdown fences if present
        if raw.startswith('```'):
            lines = raw.split('\n')
            raw = '\n'.join(lines[1:])
            if raw.endswith('```'):
                raw = raw[:-3].strip()

        plan_data = json.loads(raw)
        weeks = plan_data.get('weeks', [])
        if not weeks:
            return JsonResponse({'error': 'AI returned empty plan. Please try again.'}, status=400)

        # Deactivate old plans
        StudyPlan.objects.filter(user=request.user, is_active=True).update(is_active=False)

        plan = StudyPlan.objects.create(
            user=request.user,
            subject=subject,
            goal=goal,
            duration_weeks=duration_weeks,
            hours_per_day=hours_per_day,
        )

        import datetime
        today_date = timezone.now().date()
        # Start scheduling from the nearest upcoming Monday (or today if Monday)
        days_until_monday = (7 - today_date.weekday()) % 7
        start_monday = today_date + datetime.timedelta(days=days_until_monday)

        for week_data in weeks:
            wk_num = int(week_data.get('week', 1))
            theme = week_data.get('theme', f'Week {wk_num}')
            week_monday = start_monday + datetime.timedelta(weeks=wk_num - 1)
            for i, task in enumerate(week_data.get('tasks', [])):
                StudyPlanTask.objects.create(
                    plan=plan,
                    week_number=wk_num,
                    week_theme=theme,
                    title=task.get('title', '').strip(),
                    description=task.get('description', '').strip(),
                    order=i,
                    scheduled_date=week_monday + datetime.timedelta(days=i),
                )

        return JsonResponse({'plan': _serialize_plan(plan)})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'AI response could not be parsed. Please try again.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@csrf_exempt
def api_study_plan_toggle(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        task = get_object_or_404(StudyPlanTask, pk=task_id, plan__user=request.user)
        task.is_completed = not task.is_completed
        task.completed_at = timezone.now() if task.is_completed else None
        task.save()
        plan = task.plan
        total = plan.tasks.count()
        done = plan.tasks.filter(is_completed=True).count()
        return JsonResponse({
            'id': task.id,
            'is_completed': task.is_completed,
            'completed_tasks': done,
            'total_tasks': total,
            'progress_pct': round(done / total * 100) if total else 0,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@csrf_exempt
def api_study_plan_schedule(request):
    """Reschedule all tasks of the active plan from a given start date."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        import datetime
        body = json.loads(request.body)
        start_str = body.get('start_date', '').strip()
        if not start_str:
            return JsonResponse({'error': 'start_date is required'}, status=400)
        start_date = datetime.date.fromisoformat(start_str)

        plan = StudyPlan.objects.filter(user=request.user, is_active=True).first()
        if not plan:
            return JsonResponse({'error': 'No active plan found'}, status=404)

        for task in plan.tasks.all():
            task.scheduled_date = start_date + datetime.timedelta(days=(task.week_number - 1) * 7 + task.order)
            task.save()

        return JsonResponse({'plan': _serialize_plan(plan)})
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_study_plan_suggestion(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        plan = StudyPlan.objects.filter(user=request.user, is_active=True).first()
        if not plan:
            return JsonResponse({'suggestion': 'Start by creating your personalised study plan above!'})

        total = plan.tasks.count()
        done = plan.tasks.filter(is_completed=True).count()
        pct = round(done / total * 100) if total else 0

        # Find current week (first week with incomplete tasks)
        current_week = None
        for task in plan.tasks.filter(is_completed=False):
            current_week = task.week_number
            break

        # Build a brief status for the prompt
        weeks_status = []
        for wk in range(1, plan.duration_weeks + 1):
            wk_tasks = plan.tasks.filter(week_number=wk)
            wk_done = wk_tasks.filter(is_completed=True).count()
            wk_total = wk_tasks.count()
            weeks_status.append(f"Week {wk}: {wk_done}/{wk_total} tasks done")

        prompt = f"""A student is following a {plan.duration_weeks}-week study plan for {plan.subject}.
Goal: {plan.goal or 'Master the subject'}
Overall progress: {done}/{total} tasks ({pct}%)
{chr(10).join(weeks_status)}
Current focus: Week {current_week or plan.duration_weeks}

Give 2–3 sentences of motivating, specific study advice based on their current progress.
Be encouraging, practical, and personalised. No bullet points — just flowing text."""

        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.8,
            max_tokens=150,
        )
        suggestion = resp.choices[0].message.content.strip()
        return JsonResponse({'suggestion': suggestion, 'progress_pct': pct})
    except Exception as e:
        return JsonResponse({'suggestion': 'Keep going — every task completed brings you closer to your goal!'})


# ─── Calendar API ────────────────────────────────────────────────────────────

@login_required
def api_calendar(request):
    """Return activity data + reminders for a given year/month."""
    import calendar as cal_mod
    from django.db.models import Count
    from django.db.models.functions import TruncDate

    try:
        year  = int(request.GET.get('year',  timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        return JsonResponse({'error': 'Invalid year/month'}, status=400)

    # Month bounds (UTC)
    import datetime
    first = datetime.date(year, month, 1)
    last_day = cal_mod.monthrange(year, month)[1]
    last = datetime.date(year, month, last_day)

    user = request.user

    # --- Activity: chat messages sent by user ---
    chat_days = (
        ChatHistory.objects
        .filter(user=user, role='user',
                timestamp__date__gte=first, timestamp__date__lte=last)
        .annotate(day=TruncDate('timestamp'))
        .values('day').annotate(n=Count('id'))
    )

    # --- Activity: flashcard reviews ---
    fc_days = (
        FlashcardReview.objects
        .filter(user=user,
                reviewed_at__date__gte=first, reviewed_at__date__lte=last)
        .annotate(day=TruncDate('reviewed_at'))
        .values('day').annotate(n=Count('id'))
    )

    # --- Activity: quiz attempts ---
    quiz_days = (
        QuizAttempt.objects
        .filter(user=user,
                attempted_at__date__gte=first, attempted_at__date__lte=last)
        .annotate(day=TruncDate('attempted_at'))
        .values('day').annotate(n=Count('id'))
    )

    # --- Study plan tasks completed ---
    task_days = (
        StudyPlanTask.objects
        .filter(plan__user=user, is_completed=True,
                completed_at__date__gte=first, completed_at__date__lte=last)
        .annotate(day=TruncDate('completed_at'))
        .values('day').annotate(n=Count('id'))
    )

    # Merge into per-day dict
    activity = {}
    for row in chat_days:
        d = str(row['day'])
        activity.setdefault(d, {'chat': 0, 'flashcards': 0, 'quizzes': 0, 'tasks': 0})
        activity[d]['chat'] += row['n']
    for row in fc_days:
        d = str(row['day'])
        activity.setdefault(d, {'chat': 0, 'flashcards': 0, 'quizzes': 0, 'tasks': 0})
        activity[d]['flashcards'] += row['n']
    for row in quiz_days:
        d = str(row['day'])
        activity.setdefault(d, {'chat': 0, 'flashcards': 0, 'quizzes': 0, 'tasks': 0})
        activity[d]['quizzes'] += row['n']
    for row in task_days:
        d = str(row['day'])
        activity.setdefault(d, {'chat': 0, 'flashcards': 0, 'quizzes': 0, 'tasks': 0})
        activity[d]['tasks'] += row['n']

    # Total per day (for intensity shading)
    for d in activity:
        activity[d]['total'] = sum(activity[d].values())

    # --- Reminders for this month ---
    reminders = list(
        Reminder.objects
        .filter(user=user, date__gte=first, date__lte=last)
        .values('id', 'title', 'date', 'time', 'is_done')
    )
    for r in reminders:
        r['date'] = str(r['date'])
        r['time'] = str(r['time'])[:5] if r['time'] else None

    # Today's streak: consecutive active days up to today
    today = timezone.now().date()
    streak = 0
    check = today
    all_active = set(activity.keys())
    # Also check previous months for streak continuity
    all_active_global = set()
    for Model, field in [
        (ChatHistory, 'timestamp'), (FlashcardReview, 'reviewed_at'), (QuizAttempt, 'attempted_at')
    ]:
        qs = Model.objects.filter(user=user).annotate(day=TruncDate(field)).values_list('day', flat=True).distinct()
        all_active_global.update(str(d) for d in qs)
    task_active = StudyPlanTask.objects.filter(
        plan__user=user, is_completed=True, completed_at__isnull=False
    ).annotate(day=TruncDate('completed_at')).values_list('day', flat=True).distinct()
    all_active_global.update(str(d) for d in task_active)

    while str(check) in all_active_global:
        streak += 1
        check -= datetime.timedelta(days=1)

    # Scheduled plan tasks for this month (pending + completed)
    active_plan = StudyPlan.objects.filter(user=user, is_active=True).first()
    scheduled_tasks = {}
    if active_plan:
        for task in active_plan.tasks.filter(scheduled_date__gte=first, scheduled_date__lte=last):
            ds = str(task.scheduled_date)
            scheduled_tasks.setdefault(ds, []).append({
                'id': task.id,
                'title': task.title,
                'is_completed': task.is_completed,
                'week_number': task.week_number,
            })

    return JsonResponse({
        'year': year,
        'month': month,
        'activity': activity,
        'reminders': reminders,
        'scheduled_tasks': scheduled_tasks,
        'streak': streak,
        'today': str(today),
    })


@login_required
@csrf_exempt
def api_reminders(request):
    if request.method == 'GET':
        reminders = list(
            Reminder.objects.filter(user=request.user)
            .values('id', 'title', 'date', 'time', 'is_done')
        )
        for r in reminders:
            r['date'] = str(r['date'])
            r['time'] = str(r['time'])[:5] if r['time'] else None
        return JsonResponse({'reminders': reminders})

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            title = body.get('title', '').strip()
            date  = body.get('date', '')
            time  = body.get('time') or None
            if not title or not date:
                return JsonResponse({'error': 'title and date are required'}, status=400)
            r = Reminder.objects.create(user=request.user, title=title, date=date, time=time)
            return JsonResponse({
                'id': r.id, 'title': r.title,
                'date': str(r.date), 'time': str(r.time)[:5] if r.time else None,
                'is_done': r.is_done,
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_reminder_detail(request, pk):
    r = get_object_or_404(Reminder, pk=pk, user=request.user)

    if request.method == 'DELETE':
        r.delete()
        return JsonResponse({'msg': 'deleted'})

    if request.method == 'POST':
        r.is_done = not r.is_done
        r.save()
        return JsonResponse({'id': r.id, 'is_done': r.is_done})

    return JsonResponse({'error': 'Method not allowed'}, status=405)
