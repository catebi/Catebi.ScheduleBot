import asyncio
import logging
import threading
import time
from functools import wraps

from pyairtable.orm import Model

from app.models import Notification, Schedule, Settings, Volunteer

# Logging is configured centrally in app.logging_setup (imported by the entrypoint).

# Thread-local storage for context
_thread_local = threading.local()


def airtable_context(name):
    """Decorator to set context for Airtable operations"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            _thread_local.context = name
            try:
                return await func(*args, **kwargs)
            finally:
                _thread_local.context = None

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            _thread_local.context = name
            try:
                return func(*args, **kwargs)
            finally:
                _thread_local.context = None

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def get_model_class(func, args):
    """Helper function to determine the model class from the function and arguments"""
    # If it's a bound method, get the class from __self__
    if hasattr(func, "__self__"):
        if isinstance(func.__self__, type):
            return func.__self__.__name__
        elif isinstance(func.__self__, Model):
            return func.__self__.__class__.__name__

    # If it's a class method, args[0] should be the class
    if args and isinstance(args[0], type) and issubclass(args[0], Model):
        return args[0].__name__

    # If it's an instance method, args[0] should be the instance
    if args and isinstance(args[0], Model):
        return args[0].__class__.__name__

    return "Unknown"


def format_request_params(args, kwargs):
    """Format request parameters for logging"""
    params = []

    # Add formula if present
    if "formula" in kwargs:
        params.append(f"formula={kwargs['formula']}")

    # Add fields if present
    if "fields" in kwargs:
        params.append(f"fields={kwargs['fields']}")

    # Add sort if present
    if "sort" in kwargs:
        params.append(f"sort={kwargs['sort']}")

    return ", ".join(params) if params else "no params"


def log_airtable_request(func):
    """Decorator to log Airtable API requests"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            status = "success"
            return result
        except Exception as e:
            duration = time.time() - start_time
            status = "error"
            error_msg = str(e)
            raise
        finally:
            context = getattr(_thread_local, "context", "Unknown")
            model_class = get_model_class(func, args)
            params = format_request_params(args, kwargs)

            log_msg = (
                f"Airtable API Request - Context: {context} - "
                f"Model: {model_class} - "
                f"Function: {func.__name__} - "
                f"Params: {params} - "
                f"Duration: {duration:.2f}s - "
                f"Status: {status}"
            )

            if status == "error":
                log_msg += f" - Error: {error_msg}"

            logging.info(log_msg)

    return wrapper


# Monkey patch the model class methods to add logging
def patch_model_methods():
    methods_to_patch = ["all", "first", "get", "save", "delete", "create", "update"]

    # List of model classes to patch
    model_classes = [Volunteer, Schedule, Notification, Settings]

    for model_class in model_classes:
        for method_name in methods_to_patch:
            if hasattr(model_class, method_name):
                original_method = getattr(model_class, method_name)
                setattr(model_class, method_name, log_airtable_request(original_method))
