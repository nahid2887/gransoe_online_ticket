from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiParameter

class GlobalParameterSchema(AutoSchema):
    """
    Custom AutoSchema that automatically injects the Accept-Language header
    as a parameter to all API endpoints documented in Swagger/OpenAPI.
    """
    def get_override_parameters(self):
        params = super().get_override_parameters()
        params.append(
            OpenApiParameter(
                name="Accept-Language",
                location=OpenApiParameter.HEADER,
                description="Language code to get translated content (e.g., 'da' for Danish, 'en' for English).",
                required=False,
                type=str,
            )
        )
        return params
