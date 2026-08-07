from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings
import resend

class ContactUsView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        name = request.data.get("name")
        email = request.data.get("email")
        message = request.data.get("message")
        
        if not name or not email or not message:
            return Response(
                {"error": "Missing required fields (name, email, message)"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Assumes you have RESEND_API_KEY in your Django settings
            resend.api_key = getattr(settings, 'RESEND_API_KEY', '')
            
            if not resend.api_key:
                return Response(
                    {"error": "Resend API key not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            resend.Emails.send({
                "from": "onboarding@resend.dev", # Or replace with your verified Resend domain, e.g. "noreply@letusecho.com"
                "to": "sunnexajayi@gmail.com",
                "subject": "ECHO CONTACT US FROM",
                "html": f"<h3>New Contact Form Submission</h3><p><strong>Name:</strong> {name}</p><p><strong>Email:</strong> {email}</p><p><strong>Message:</strong><br/>{message}</p>"
            })
            return Response({"success": True, "message": "Email sent successfully"}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to send email: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
