from django.urls import path
from . import views

urlpatterns = [
    path("", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("customers/<str:cid>/", views.customer_detail, name="customer_detail"),
    path("calculate/", views.calculate_view, name="calculate"),
    path("calculate/all/", views.calculate_all, name="calculate_all"),
    path("download/", views.download_excel, name="download_excel"),
]
