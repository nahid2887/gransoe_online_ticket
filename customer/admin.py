from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'get_email', 'phone_number', 'gender', 'date_of_birth', 'created_at')
    search_fields = ('full_name', 'user__email', 'phone_number')
    list_filter = ('gender', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
