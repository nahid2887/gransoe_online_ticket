import json
from django.utils import translation
from config.translator import translate_to_danish

class TranslationMiddleware:
    """
    Middleware that dynamically translates JSON API response values from English to Danish
    when the active request language is Danish ('da').
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Only apply translation for API responses, excluding API documentation/schemas
        path = request.path
        if path.startswith('/api/') and not path.startswith(('/api/schema/', '/api/docs/', '/api/redoc/')):
            lang = translation.get_language()
            if lang and lang.startswith('da'):
                content_type = response.get('Content-Type', '')
                if 'application/json' in content_type and getattr(response, 'content', None):
                    try:
                        data = json.loads(response.content.decode('utf-8'))
                        translated_data = self.translate_data(data)
                        
                        # Sync response.data for compatibility with tests / DRF internal checks
                        if hasattr(response, 'data'):
                            response.data = translated_data

                        # Re-render content
                        response.content = json.dumps(translated_data, ensure_ascii=False).encode('utf-8')
                        response['Content-Length'] = str(len(response.content))
                    except Exception:
                        pass
        return response

    def translate_data(self, data):
        """
        Recursively traverses dictionary/list structure and translates eligible strings.
        """
        if isinstance(data, dict):
            # Keys that should not have their values translated
            skip_keys = {
                'email', 'username', 'image', 'qr_image', 'qr_data', 'checkout_url', 
                'client_secret', 'stripe_payment_intent', 'code', 'tracking_number', 
                'phone_number', 'date_of_birth', 'created_at', 'updated_at', 
                'date', 'time', 'reservation_expires_at', 'access_token', 'refresh_token', 
                'id', 'user_id', 'event_id', 'quantity', 'price_per_ticket', 'total_amount', 
                'platform_fee', 'ticketing_fee', 'role', 'gender', 'avatar', 'avatar_url', 
                'external_url', 'status', 'payment_status', 'otp', 'is_verified', 
                'verified_at', 'is_superuser', 'is_staff', 'date_joined', 'tickets_sold', 
                'active_events', 'checked_in'
            }

            new_data = {}
            for key, val in data.items():
                key_lower = key.lower()
                # Determine if we should skip translating this key's value
                if (key_lower in skip_keys or 
                    key_lower.endswith(('_id', 'id', '_url', 'url', '_email', 'email', '_at', '_date', '_time', 'token', 'otp'))):
                    new_data[key] = val
                else:
                    new_data[key] = self.translate_data(val)
            return new_data

        elif isinstance(data, list):
            return [self.translate_data(item) for item in data]

        elif isinstance(data, str):
            stripped = data.strip()
            if not stripped:
                return data
            # Avoid translating URLs or file paths
            if stripped.startswith(('http://', 'https://', '/media/')):
                return data
            return translate_to_danish(data)

        return data
