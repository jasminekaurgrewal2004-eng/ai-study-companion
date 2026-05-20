from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_page, name='login'),
    
    # API Endpoints
    path('api/auth/signup/', views.api_signup, name='api_signup'),
    path('api/auth/login/', views.api_login, name='api_login'),
    path('api/auth/logout/', views.api_logout, name='logout'),
    path('api/profile/', views.api_profile, name='api_profile'),
    path('api/journals/', views.api_journals, name='api_journals'),
    path('api/journals/<int:pk>/', views.api_journal_detail, name='api_journal_detail'),
    path('api/chat/', views.api_chat, name='api_chat'),
    path('api/chat/sessions/', views.api_chat_sessions, name='api_chat_sessions'),
    path('api/chat/sessions/<int:pk>/', views.api_chat_session_detail, name='api_chat_session_detail'),

    # Syllabus API
    path('api/syllabi/', views.api_syllabi, name='api_syllabi'),
    path('api/syllabi/<int:pk>/', views.api_syllabus_detail, name='api_syllabus_detail'),
    path('api/syllabi/<int:pk>/items/', views.api_syllabus_add_item, name='api_syllabus_add_item'),
    path('api/syllabi/<int:pk>/items/<int:item_id>/', views.api_syllabus_delete_item, name='api_syllabus_delete_item'),
    path('api/syllabi/<int:pk>/insights/', views.api_syllabus_insights, name='api_syllabus_insights'),
    path('api/syllabi/<int:pk>/plan-chat/', views.api_syllabus_plan_chat, name='api_syllabus_plan_chat'),
    path('api/syllabi/<int:pk>/monthly-plan/', views.api_syllabus_monthly_plan, name='api_syllabus_monthly_plan'),
    path('api/syllabi/<int:pk>/monthly-plan-chat/', views.api_syllabus_monthly_plan_chat, name='api_syllabus_monthly_plan_chat'),

    # Flashcard API
    path('api/flashcard-subjects/', views.api_flashcard_subjects, name='api_flashcard_subjects'),
    path('api/flashcards/', views.api_flashcards, name='api_flashcards'),
    path('api/flashcards/<int:pk>/', views.api_flashcard_detail, name='api_flashcard_detail'),
    path('api/flashcards/<int:pk>/review/', views.api_flashcard_review, name='api_flashcard_review'),
    path('api/flashcards/generate/', views.api_generate_flashcards, name='api_generate_flashcards'),

    # DS Insights API
    path('api/predict-recall/', views.api_predict_recall, name='api_predict_recall'),
    path('api/confusion-map/', views.api_confusion_map, name='api_confusion_map'),
    path('api/risk-score/', views.api_risk_score, name='api_risk_score'),
    path('api/quiz-attempt/', views.api_quiz_attempt, name='api_quiz_attempt'),

    # Study Plan API
    path('api/study-plan/', views.api_study_plan, name='api_study_plan'),
    path('api/study-plan/generate/', views.api_study_plan_generate, name='api_study_plan_generate'),
    path('api/study-plan/tasks/<int:task_id>/toggle/', views.api_study_plan_toggle, name='api_study_plan_toggle'),
    path('api/study-plan/schedule/', views.api_study_plan_schedule, name='api_study_plan_schedule'),
    path('api/study-plan/suggestion/', views.api_study_plan_suggestion, name='api_study_plan_suggestion'),

    # Calendar API
    path('api/calendar/', views.api_calendar, name='api_calendar'),
    path('api/reminders/', views.api_reminders, name='api_reminders'),
    path('api/reminders/<int:pk>/', views.api_reminder_detail, name='api_reminder_detail'),
]
