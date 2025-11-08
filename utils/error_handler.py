"""
Centralized error handling utilities for consistent API responses
"""
import logging
from rest_framework import status
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from django.db import IntegrityError


logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling class for consistent API responses"""
    
    @staticmethod
    def format_error_response(error_message, details=None, status_code=status.HTTP_400_BAD_REQUEST):
        """
        Format standardized error response
        
        Args:
            error_message (str): Main error message
            details (str): Detailed error information
            status_code (int): HTTP status code
            
        Returns:
            Response: Formatted error response
        """
        response_data = {
            'success': False,
            'error': error_message,
            'details': details or error_message
        }
        
        return Response(response_data, status=status_code)
    
    @staticmethod
    def handle_validation_error(serializer_errors, custom_message=None):
        """
        Handle Django serializer validation errors
        
        Args:
            serializer_errors (dict): Serializer validation errors
            custom_message (str): Custom error message
            
        Returns:
            Response: Formatted error response
        """
        error_message = custom_message or "Validation failed"
        
        # Convert serializer errors to readable string format
        details_list = []
        for field, errors in serializer_errors.items():
            if isinstance(errors, list):
                for error in errors:
                    if field == 'non_field_errors':
                        details_list.append(str(error))
                    else:
                        # Format field name to be more readable
                        field_name = field.replace('_', ' ').title()
                        details_list.append(f"{field_name}: {error}")
            else:
                if field == 'non_field_errors':
                    details_list.append(str(errors))
                else:
                    # Format field name to be more readable
                    field_name = field.replace('_', ' ').title()
                    details_list.append(f"{field_name}: {errors}")
        
        # Join all errors into a single readable string
        details = ". ".join(details_list) if details_list else error_message
        
        return ErrorHandler.format_error_response(
            error_message,
            details,
            status.HTTP_400_BAD_REQUEST
        )
    
    @staticmethod
    def handle_database_error(exception, operation="database operation"):
        """
        Handle database-related errors
        
        Args:
            exception (Exception): Database exception
            operation (str): Description of the operation that failed
            
        Returns:
            Response: Formatted error response
        """
        logger.error(f"Database error during {operation}: {str(exception)}")
        
        if isinstance(exception, IntegrityError):
            error_message = f"Data integrity error during {operation}"
            details = "The operation conflicts with existing data constraints"
        else:
            error_message = f"Database error during {operation}"
            details = f"Failed to complete {operation}. Please try again."
        
        return ErrorHandler.format_error_response(
            error_message,
            details,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    @staticmethod
    def handle_authentication_error(custom_message=None):
        """
        Handle authentication errors
        
        Args:
            custom_message (str): Custom error message
            
        Returns:
            Response: Formatted error response
        """
        error_message = custom_message or "Authentication required"
        details = "Please provide valid authentication credentials"
        
        return ErrorHandler.format_error_response(
            error_message,
            details,
            status.HTTP_401_UNAUTHORIZED
        )
    
    @staticmethod
    def handle_permission_error(custom_message=None):
        """
        Handle permission errors
        
        Args:
            custom_message (str): Custom error message
            
        Returns:
            Response: Formatted error response
        """
        error_message = custom_message or "Permission denied"
        details = "You don't have permission to perform this action"
        
        return ErrorHandler.format_error_response(
            error_message,
            details,
            status.HTTP_403_FORBIDDEN
        )
    
    @staticmethod
    def handle_not_found_error(resource_name="Resource", custom_message=None):
        """
        Handle not found errors
        
        Args:
            resource_name (str): Name of the resource that wasn't found
            custom_message (str): Custom error message
            
        Returns:
            Response: Formatted error response
        """
        error_message = custom_message or f"{resource_name} not found"
        details = f"The requested {resource_name.lower()} could not be found"
        
        return ErrorHandler.format_error_response(
            error_message,
            details,
            status.HTTP_404_NOT_FOUND
        )
    
    @staticmethod
    def handle_file_error(operation="file operation", custom_message=None):
        """
        Handle file-related errors
        
        Args:
            operation (str): Description of the file operation
            custom_message (str): Custom error message
            
        Returns:
            Response: Formatted error response
        """
        error_message = custom_message or f"File error during {operation}"
        details = f"Failed to complete {operation}. Please check the file format and try again."
        
        return ErrorHandler.format_error_response(
            error_message,
            details,
            status.HTTP_400_BAD_REQUEST
        )
    
    @staticmethod
    def handle_external_api_error(service_name, exception, operation="API call"):
        """
        Handle external API errors (like Gemini AI)
        
        Args:
            service_name (str): Name of the external service
            exception (Exception): Exception from external service
            operation (str): Description of the operation
            
        Returns:
            Response: Formatted error response
        """
        logger.error(f"{service_name} error during {operation}: {str(exception)}")
        
        error_message = f"{service_name} service error"
        details = f"Failed to complete {operation} using {service_name}. Please try again later."
        
        return ErrorHandler.format_error_response(
            error_message,
            details,
            status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    @staticmethod
    def handle_generic_error(exception, operation="operation"):
        """
        Handle generic unexpected errors
        
        Args:
            exception (Exception): The exception that occurred
            operation (str): Description of the operation that failed
            
        Returns:
            Response: Formatted error response
        """
        logger.error(f"Unexpected error during {operation}: {str(exception)}")
        
        error_message = f"Unexpected error during {operation}"
        details = "An unexpected error occurred. Please try again later."
        
        return ErrorHandler.format_error_response(
            error_message,
            details,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    @staticmethod
    def success_response(data, message="Operation completed successfully", status_code=status.HTTP_200_OK):
        """
        Format standardized success response
        
        Args:
            data (dict): Response data
            message (str): Success message
            status_code (int): HTTP status code
            
        Returns:
            Response: Formatted success response
        """
        response_data = {
            'success': True,
            'message': message,
            **data
        }
        
        return Response(response_data, status=status_code)