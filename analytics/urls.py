from django.urls import path
from . import views

urlpatterns = [
    path('review-queue/', views.review_queue, name='analytics_review_queue'),
    path('confusion-map/', views.confusion_map, name='analytics_confusion_map'),
    path('risk-score/', views.risk_score, name='analytics_risk_score'),
    path('log-review/', views.log_review, name='analytics_log_review'),
    path('smart-topics/', views.smart_topics, name='analytics_smart_topics'),
    path('generate-quiz/', views.generate_quiz, name='analytics_generate_quiz'),
    path('generate-mock/', views.generate_mock, name='analytics_generate_mock'),
    path('video-search/', views.video_search, name='analytics_video_search'),
    path('study-time/', views.study_time, name='analytics_study_time'),
]
