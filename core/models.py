from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class JournalEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='journals')
    title = models.CharField(max_length=255)
    content = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    mood = models.CharField(max_length=50, blank=True, null=True)
    is_protected = models.BooleanField(default=False)
    entry_password = models.CharField(max_length=128, blank=True, null=True) # Simple for now

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-date']

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=200, default='New Conversation')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} — {self.title}"

    class Meta:
        ordering = ['-updated_at']


class ChatHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chats')
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    role = models.CharField(max_length=50)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.role} - {self.timestamp}"

    class Meta:
        ordering = ['timestamp']


class Syllabus(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='syllabi')
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = 'Syllabi'


class SyllabusItem(models.Model):
    ITEM_TYPES = [
        ('text', 'Text Note'),
        ('image', 'Image'),
        ('file', 'File'),
        ('link', 'Link'),
        ('pdf', 'PDF'),
        ('audio', 'Audio'),
        ('video', 'Video'),
    ]
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=10, choices=ITEM_TYPES, default='text')
    content = models.TextField(blank=True, default='')  # For text notes / captions
    image = models.ImageField(upload_to='syllabus_images/', blank=True, null=True)
    file = models.FileField(upload_to='syllabus_files/', blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, default='')
    file_size = models.BigIntegerField(default=0)  # bytes
    file_type = models.CharField(max_length=100, blank=True, default='')  # MIME type
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item_type} - {self.syllabus.title}"

    class Meta:
        ordering = ['order', 'created_at']


class Flashcard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flashcards')
    syllabus_item = models.ForeignKey('SyllabusItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='flashcards')
    front = models.TextField()
    back = models.TextField()
    subject = models.CharField(max_length=100, blank=True, default='General')
    # SM-2 spaced repetition state
    interval = models.IntegerField(default=1)        # days until next review
    ease_factor = models.FloatField(default=2.5)     # difficulty multiplier (1.3–2.5)
    repetitions = models.IntegerField(default=0)     # consecutive successful reviews
    next_review = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.front[:50]}"

    class Meta:
        ordering = ['next_review']


class FlashcardReview(models.Model):
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flashcard_reviews')
    grade = models.IntegerField()           # 0=blackout, 1=wrong, 2=hard, 3=ok, 4=good, 5=perfect
    days_since_last = models.FloatField(default=0)
    reviewed_at = models.DateTimeField(auto_now_add=True)
    response_time_ms = models.IntegerField(default=0)

    def __str__(self):
        return f"Card {self.flashcard_id} grade={self.grade}"

    class Meta:
        ordering = ['-reviewed_at']


class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    subject = models.CharField(max_length=100, blank=True, default='General')
    score = models.FloatField()              # 0–100
    total_questions = models.IntegerField(default=10)
    correct_answers = models.IntegerField(default=0)
    time_taken_seconds = models.IntegerField(default=0)
    attempted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.score:.0f}% — {self.attempted_at.date()}"

    class Meta:
        ordering = ['-attempted_at']


class PredictionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prediction_logs')
    feature_name = models.CharField(max_length=100)
    payload_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class StudyPattern(models.Model):
    """Per-user computed peak-focus window derived from activity timestamps."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='study_pattern')
    peak_hour_start = models.IntegerField(default=0)       # local hour 0-23
    peak_hour_end = models.IntegerField(default=2)         # local hour 0-23 (exclusive)
    peak_days = models.JSONField(default=list)             # weekday ints 0=Mon…6=Sun (top-3)
    weekly_intensity = models.JSONField(default=dict)      # {day_str: {hour_str: float}} 0-1
    productivity_score = models.FloatField(default=0.0)   # 0-1 weighted composite
    confidence = models.FloatField(default=0.0)            # min(1.0, n_events / 50)
    computed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user.username} — peak {self.peak_hour_start}–{self.peak_hour_end}h"

    class Meta:
        verbose_name = 'Study Pattern'


class StudyPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_plans')
    subject = models.CharField(max_length=200)
    goal = models.TextField(blank=True, default='')
    duration_weeks = models.IntegerField(default=4)
    hours_per_day = models.FloatField(default=2.0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.subject}"


class StudyPlanTask(models.Model):
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name='tasks')
    week_number = models.IntegerField()
    week_theme = models.CharField(max_length=200, blank=True, default='')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default='')
    scheduled_date = models.DateField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['week_number', 'order']

    def __str__(self):
        return f"Week {self.week_number}: {self.title}"


class Reminder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=200)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.user.username} — {self.title} on {self.date}"

