import logging
import time
import os
import inspect
from functools import wraps
from pyairtable.orm import Model
from airtable_model import Volunteer, Schedule, Notification, Settings

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/airtable.log')
    ]
)

def get_calling_function():
    """Get the name of the function that called the Airtable API"""
    stack = inspect.stack()
    # Skip the first 3 frames (this function, wrapper, and the Airtable method)
    for frame in stack[3:]:
        if frame.filename.endswith('bot.py'):
            # If we're at module level, try to get the context from the previous frame
            if frame.function == '<module>':
                # Look at the code context to understand what's happening
                context = frame.code_context
                if context:
                    # Try to find a meaningful line from the context
                    for line in context:
                        if line and any(keyword in line for keyword in [
                            'update_volunteers', 'send_notifications', 'schedule_handler', 
                            'help_handler', 'callback_handler', 'start_handler', 'send_curator_notifications'
                        ]):
                            return line.strip()
            
            # If we found a function name, return it
            if frame.function != '<module>':
                return frame.function
            
            # If we're still at module level, look at the previous frame
            prev_frame = frame.f_back
            if prev_frame and prev_frame.f_code.co_filename.endswith('bot.py'):
                if prev_frame.function != '<module>':
                    return prev_frame.function
                
                # Look at the previous frame's context
                prev_context = prev_frame.f_code.co_code
                if prev_context:
                    # Try to find a meaningful line from the previous frame's context
                    for line in prev_frame.code_context or []:
                        if line and any(keyword in line for keyword in [
                            'update_volunteers', 'send_notifications', 'schedule_handler', 
                            'help_handler', 'callback_handler', 'start_handler', 'send_curator_notifications'
                        ]):
                            return line.strip()
    
    return "Unknown"

def get_model_class(func, args):
    """Helper function to determine the model class from the function and arguments"""
    # Debug logging
    logging.debug(f"Function: {func.__name__}")
    logging.debug(f"Function type: {type(func)}")
    logging.debug(f"Has __self__: {hasattr(func, '__self__')}")
    if hasattr(func, '__self__'):
        logging.debug(f"__self__ type: {type(func.__self__)}")
    
    # If it's a bound method, get the class from __self__
    if hasattr(func, '__self__'):
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

def log_airtable_request(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            # Get the model class name and method name
            method_name = func.__name__
            model_class = get_model_class(func, args)
            calling_function = get_calling_function()
            
            # Log the request details before execution
            logging.info(
                f"Airtable API Request - Model: {model_class}, Method: {method_name}, "
                f"Triggered by: {calling_function}, Starting request..."
            )
            
            result = func(*args, **kwargs)
            end_time = time.time()
            duration = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            
            # Log the request details after successful execution
            logging.info(
                f"Airtable API Request - Model: {model_class}, Method: {method_name}, "
                f"Triggered by: {calling_function}, Duration: {duration}ms, Status: Success"
            )
            return result
        except Exception as e:
            end_time = time.time()
            duration = round((end_time - start_time) * 1000, 2)
            logging.error(
                f"Airtable API Request - Model: {model_class}, Method: {method_name}, "
                f"Triggered by: {calling_function}, Duration: {duration}ms, Status: Error, Error: {str(e)}"
            )
            raise
    return wrapper

# Monkey patch the model class methods to add logging
def patch_model_methods():
    methods_to_patch = [
        'all', 'first', 'get', 'save', 'delete', 'create', 'update'
    ]
    
    # List of model classes to patch
    model_classes = [Volunteer, Schedule, Notification, Settings]
    
    for model_class in model_classes:
        for method_name in methods_to_patch:
            if hasattr(model_class, method_name):
                original_method = getattr(model_class, method_name)
                setattr(model_class, method_name, log_airtable_request(original_method))

# Call this function when the module is imported
patch_model_methods() 