"""
User Services

Business logic for user authentication, OTP management, and email services.
"""

import random
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
# from allauth.account.adapter import DefaultAccountAdapter
# from allauth.account.models import EmailAddress
# from ..users_.models import EmailVerificationOTP, UserProfile

User = get_user_model()


# class CustomAccountAdapter(DefaultAccountAdapter):
#     """
#     Custom account adapter to override default allauth behavior for an API-first approach.
#     """
#     def respond_user_inactive(self, request, user):
#         """
#         This is called when a user signs up with mandatory email verification.
#         Instead of redirecting to the 'account_inactive' URL, we do nothing,
#         as dj-rest-auth will provide the appropriate JSON response.
#         """
#         return None


# class OTPService:
#     """Service for managing OTP generation, validation, and cleanup"""
    
#     @staticmethod
#     def generate_otp(length=6):
#         """Generate a random OTP code"""
#         return ''.join(random.choices(string.digits, k=length))
    
#     @staticmethod
#     def create_otp(user, purpose='verification'):
#         """Create and save OTP for user"""
#         # Clean up old OTPs for this user and purpose
#         EmailVerificationOTP.objects.filter(
#             user=user,
#             purpose=purpose,
#             is_used=False
#         ).update(is_used=True)
        
#         # Generate new OTP
#         otp_code = OTPService.generate_otp(settings.OTP_LENGTH)
#         expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        
#         otp = EmailVerificationOTP.objects.create(
#             user=user,
#             otp_code=otp_code,
#             purpose=purpose,
#             expires_at=expires_at
#         )
        
#         return otp
    
#     @staticmethod
#     def validate_otp(user, otp_code, purpose='verification'):
#         """Validate OTP for user"""
#         otp = EmailVerificationOTP.objects.filter(
#             user=user,
#             otp_code=otp_code,
#             purpose=purpose,
#             is_used=False
#         ).first()
        
#         if otp and otp.is_valid():
#             otp.is_used = True
#             otp.save()
#             return True
        
#         return False
    
#     @staticmethod
#     def cleanup_expired_otps():
#         """Clean up expired OTPs (can be run as a periodic task)"""
#         expired_otps = EmailVerificationOTP.objects.filter(
#             expires_at__lt=timezone.now()
#         )
#         count = expired_otps.count()
#         expired_otps.delete()
#         return count




class EmailService:
    """Service for sending various types of emails"""
    
    @staticmethod
    def send_verification_email(user, otp_code):
        """Send email verification OTP"""
        subject = 'Verify Your Email - OCR & Voice Translation API'
        message = f'''
Hello {user.get_full_name() or user.email},

Thank you for registering with ECHO!

Your email verification code is: {otp_code}

This code will expire in {settings.OTP_EXPIRY_MINUTES} minutes.

If you didn't request this verification, please ignore this email.

Best regards,
OCR & Voice Translation API Team
        '''
        
        return EmailService._send_email(user.email, subject, message)
    
    @staticmethod
    def send_password_reset_email(user, otp_code):
        """Send password reset OTP"""
        subject = 'Password Reset Request - OCR & Voice Translation API'
        message = f'''
Hello {user.get_full_name() or user.email},

We received a request to reset your password for your OCR & Voice Translation API account.

Your password reset code is: {otp_code}

This code will expire in {settings.OTP_EXPIRY_MINUTES} minutes.

If you didn't request a password reset, please ignore this email and your password will remain unchanged.

Best regards,
OCR & Voice Translation API Team
        '''
        
        return EmailService._send_email(user.email, subject, message)
    
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email after successful verification"""
        subject = 'Welcome to OCR & Voice Translation API!'
        message = f'''
Hello {user.get_full_name() or user.email},

Welcome to ECHO ! Your email has been successfully verified.

You now have access to our comprehensive API services:
- Image OCR with text extraction and translation
- Voice translation with African language specialization
- Support for 22+ languages including African languages

Get started by logging in and exploring our API documentation.

Best regards,
OCR & Voice Translation API Team
        '''
        
        return EmailService._send_email(user.email, subject, message)
    
    @staticmethod
    def send_password_changed_email(user):
        """Send notification when password is changed"""
        subject = 'Password Changed - OCR & Voice Translation API'
        message = f'''
Hello {user.get_full_name() or user.email},

Your password for OCR & Voice Translation API has been successfully changed.

If you didn't make this change, please contact our support team immediately.

Best regards,
OCR & Voice Translation API Team
        '''
        
        return EmailService._send_email(user.email, subject, message)
    
    @staticmethod
    def _send_email(to_email, subject, message):
        """Internal method to send email"""
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False


# class UserAuthService:
#     """Service for user authentication operations"""
    
#     @staticmethod
#     def register_user(email, password, **extra_fields):
#         """Register new user and send verification email"""
#         # Create user
#         user = User.objects.create_user(
#             email=email,
#             password=password,
#             **extra_fields
#         )
        
#         # Create allauth email address record to integrate with its flow
#         EmailAddress.objects.create(
#             user=user,
#             email=user.email,
#             primary=True,
#             verified=False
#         )
        
#         # Create user profile
#         UserProfile.objects.get_or_create(user=user)
        
#         # Generate and send verification OTP
#         otp = OTPService.create_otp(user, 'verification')
#         EmailService.send_verification_email(user, otp.otp_code)
        
#         return user
    
#     @staticmethod
#     def verify_email(user, otp_code):
#         """Verify user email with OTP"""
#         if OTPService.validate_otp(user, otp_code, 'verification'):
#             user.email_verified = True
#             user.is_active = True
#             user.save()
            
#             # Also verify the allauth email address record
#             try:
#                 email_address = EmailAddress.objects.get(user=user, email=user.email)
#                 email_address.verified = True
#                 email_address.set_as_primary(conditional=True)
#                 email_address.save()
#             except EmailAddress.DoesNotExist:
#                 # Fallback in case the record wasn't created during registration
#                 EmailAddress.objects.create(
#                     user=user, email=user.email, primary=True, verified=True
#                 )
            
#             # Send welcome email
#             EmailService.send_welcome_email(user)
#             return True
        
#         return False
    
#     @staticmethod
#     def request_password_reset(email):
#         """Request password reset for user"""
#         try:
#             user = User.objects.get(email=email)
#             if not user.email_verified:
#                 return False, "Please verify your email first."
            
#             # Generate and send reset OTP
#             otp = OTPService.create_otp(user, 'password_reset')
#             EmailService.send_password_reset_email(user, otp.otp_code)
#             return True, "Password reset code sent to your email."
        
#         except User.DoesNotExist:
#             return False, "User with this email does not exist."
    
#     @staticmethod
#     def reset_password(user, otp_code, new_password):
#         """Reset user password with OTP"""
#         if OTPService.validate_otp(user, otp_code, 'password_reset'):
#             user.set_password(new_password)
#             user.login_attempts = 0  # Reset login attempts
#             user.account_locked_until = None  # Unlock account
#             user.save()
            
#             # Send confirmation email
#             EmailService.send_password_changed_email(user)
#             return True
        
#         return False
    
#     @staticmethod
#     def resend_verification_otp(email):
#         """Resend verification OTP"""
#         try:
#             user = User.objects.get(email=email)
#             if user.email_verified:
#                 return False, "Email is already verified."
            
#             otp = OTPService.create_otp(user, 'verification')
#             EmailService.send_verification_email(user, otp.otp_code)
#             return True, "Verification code sent to your email."
        
#         except User.DoesNotExist:
#             return False, "User with this email does not exist."


class UserStatsService:
    """Service for user statistics and analytics"""
    
    @staticmethod
    def get_user_statistics(user=None):
        """Get user-specific or overall statistics"""
        from ocr_app.models import OCRResult, TranslationFailureLog
        from translation.models import Translation
        from datetime import timedelta
        
        now = timezone.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        if user:
            # User-specific statistics
            return UserStatsService._get_user_specific_stats(user, today, week_ago, month_ago)
        else:
            # Admin statistics - overall system stats
            return UserStatsService._get_admin_statistics(today, week_ago, month_ago)
    
    @staticmethod
    def _get_user_specific_stats(user, today, week_ago, month_ago):
        """Get statistics for a specific user"""
        from ocr_app.models import OCRResult, TranslationFailureLog
        from translation.models import Translation
        
        # OCR Statistics
        user_ocr_total = OCRResult.objects.filter(user=user).count()
        user_ocr_success = OCRResult.objects.filter(user=user, original_text__isnull=False).count()
        user_ocr_failed = user_ocr_total - user_ocr_success
        user_ocr_today = OCRResult.objects.filter(user=user, created_at__date=today).count()
        user_ocr_week = OCRResult.objects.filter(user=user, created_at__gte=week_ago).count()
        user_ocr_month = OCRResult.objects.filter(user=user, created_at__gte=month_ago).count()
        
        # Voice Translation Statistics  
        user_voice_total = Translation.objects.filter(user=user).count()
        user_voice_success = Translation.objects.filter(user=user, translated_text__isnull=False).count()
        user_voice_failed = user_voice_total - user_voice_success
        user_voice_today = Translation.objects.filter(user=user, created_at__date=today).count()
        user_voice_week = Translation.objects.filter(user=user, created_at__gte=week_ago).count()
        user_voice_month = Translation.objects.filter(user=user, created_at__gte=month_ago).count()
        
        # Calculate average confidence scores
        user_ocr_avg_confidence = OCRResult.objects.filter(
            user=user, confidence_score__isnull=False
        ).aggregate(avg_confidence=models.Avg('confidence_score'))['avg_confidence'] or 0
        
        user_voice_avg_confidence = Translation.objects.filter(
            user=user, confidence_score__isnull=False
        ).aggregate(avg_confidence=models.Avg('confidence_score'))['avg_confidence'] or 0
        
        # Calculate processing times
        user_ocr_avg_time = OCRResult.objects.filter(
            user=user, processing_time__isnull=False
        ).aggregate(avg_time=models.Avg('processing_time'))['avg_time'] or 0
        
        user_voice_avg_time = Translation.objects.filter(
            user=user, processing_time__isnull=False
        ).aggregate(avg_time=models.Avg('processing_time'))['avg_time'] or 0
        
        return {
            'user_info': {
                'email': user.email,
                'member_since': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'email_verified': user.email_verified,
            },
            'ocr_stats': {
                'total_processed': user_ocr_total,
                'successful': user_ocr_success,
                'failed': user_ocr_failed,
                'success_rate': round((user_ocr_success / max(user_ocr_total, 1)) * 100, 2),
                'processed_today': user_ocr_today,
                'processed_this_week': user_ocr_week,
                'processed_this_month': user_ocr_month,
                'average_confidence': round(user_ocr_avg_confidence, 2),
                'average_processing_time': round(user_ocr_avg_time, 2),
            },
            'voice_stats': {
                'total_translations': user_voice_total,
                'successful': user_voice_success,
                'failed': user_voice_failed,
                'success_rate': round((user_voice_success / max(user_voice_total, 1)) * 100, 2),
                'translated_today': user_voice_today,
                'translated_this_week': user_voice_week,
                'translated_this_month': user_voice_month,
                'average_confidence': round(user_voice_avg_confidence, 2),
                'average_processing_time': round(user_voice_avg_time, 2),
            },
            'usage_totals': {
                'total_operations': user_ocr_total + user_voice_total,
                'operations_today': user_ocr_today + user_voice_today,
                'operations_this_week': user_ocr_week + user_voice_week,
                'operations_this_month': user_ocr_month + user_voice_month,
            }
        }
    
    @staticmethod 
    def _get_admin_statistics(today, week_ago, month_ago):
        """Get system-wide statistics for admin"""
        from ocr_app.models import OCRResult, TranslationFailureLog
        from translation.models import Translation
        
        # User Statistics
        total_users = User.objects.count()
        verified_users = User.objects.filter(email_verified=True).count()
        active_today = User.objects.filter(last_login__date=today).count()
        active_week = User.objects.filter(last_login__gte=week_ago).count()
        active_month = User.objects.filter(last_login__gte=month_ago).count()
        
        # OCR Statistics
        total_ocr = OCRResult.objects.count()
        ocr_success = OCRResult.objects.filter(original_text__isnull=False).count()
        ocr_failed = total_ocr - ocr_success
        ocr_today = OCRResult.objects.filter(created_at__date=today).count()
        ocr_week = OCRResult.objects.filter(created_at__gte=week_ago).count()
        ocr_month = OCRResult.objects.filter(created_at__gte=month_ago).count()
        
        # Voice Translation Statistics
        total_voice = Translation.objects.count()
        voice_success = Translation.objects.filter(translated_text__isnull=False).count()
        voice_failed = total_voice - voice_success
        voice_today = Translation.objects.filter(created_at__date=today).count()
        voice_week = Translation.objects.filter(created_at__gte=week_ago).count()
        voice_month = Translation.objects.filter(created_at__gte=month_ago).count()
        
        # Translation Failure Statistics
        total_failures = TranslationFailureLog.objects.count()
        failures_today = TranslationFailureLog.objects.filter(created_at__date=today).count()
        
        # Popular languages
        from django.db.models import Count
        popular_ocr_languages = OCRResult.objects.filter(
            detected_language__isnull=False
        ).values('detected_language').annotate(
            count=Count('detected_language')
        ).order_by('-count')[:5]
        
        popular_voice_languages = Translation.objects.values('original_language').annotate(
            count=Count('original_language')
        ).order_by('-count')[:5]
        
        return {
            'system_overview': {
                'total_users': total_users,
                'verified_users': verified_users,
                'verification_rate': round((verified_users / max(total_users, 1)) * 100, 2),
                'active_users_today': active_today,
                'active_users_this_week': active_week,
                'active_users_this_month': active_month,
            },
            'ocr_analytics': {
                'total_processed': total_ocr,
                'successful': ocr_success,
                'failed': ocr_failed,
                'success_rate': round((ocr_success / max(total_ocr, 1)) * 100, 2),
                'processed_today': ocr_today,
                'processed_this_week': ocr_week,
                'processed_this_month': ocr_month,
                'popular_languages': list(popular_ocr_languages),
            },
            'voice_analytics': {
                'total_translations': total_voice,
                'successful': voice_success,
                'failed': voice_failed,
                'success_rate': round((voice_success / max(total_voice, 1)) * 100, 2),
                'translated_today': voice_today,
                'translated_this_week': voice_week,
                'translated_this_month': voice_month,
                'popular_languages': list(popular_voice_languages),
            },
            'error_analytics': {
                'total_failures': total_failures,
                'failures_today': failures_today,
                'failure_rate': round((total_failures / max(total_ocr + total_voice, 1)) * 100, 2),
            },
            'usage_totals': {
                'total_operations': total_ocr + total_voice,
                'operations_today': ocr_today + voice_today,
                'operations_this_week': ocr_week + voice_week,
                'operations_this_month': ocr_month + voice_month,
            }
        }
    
    @staticmethod
    def update_user_api_usage(user):
        """Update user API usage statistics"""
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Update daily and monthly counters
        today = timezone.now().date()
        if profile.last_api_call and profile.last_api_call.date() != today:
            profile.api_calls_today = 1
        else:
            profile.api_calls_today += 1
        
        profile.api_calls_this_month += 1
        profile.last_api_call = timezone.now()
        profile.save()
        
        return profile


class SecurityService:
    """Service for security-related operations"""
    
    @staticmethod
    def check_account_security(user, request_ip=None):
        """Check account security status"""
        # Check if account is locked
        if user.is_account_locked():
            return False, f"Account locked until {user.account_locked_until}"
        
        # Check if email is verified
        if not user.email_verified:
            return False, "Please verify your email first"
        
        return True, "Account security check passed"
    
    @staticmethod
    def handle_failed_login(user, request_ip=None):
        """Handle failed login attempt"""
        user.login_attempts += 1
        user.last_failed_login = timezone.now()
        
        # Lock account after 5 failed attempts
        if user.login_attempts >= 5:
            user.account_locked_until = timezone.now() + timedelta(minutes=30)
        
        user.save()
    
    @staticmethod
    def handle_successful_login(user, request_ip=None):
        """Handle successful login"""
        user.login_attempts = 0
        user.last_login = timezone.now()
        user.account_locked_until = None
        user.save()
