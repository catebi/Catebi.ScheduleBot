import logging
import time
import os
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

def get_model_class(func, args):
    """Helper function to determine the model class from the function and arguments"""
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
            
            result = func(*args, **kwargs)
            end_time = time.time()
            duration = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            
            # Log the request details
            logging.info(
                f"Airtable API Request - Model: {model_class}, Method: {method_name}, "
                f"Duration: {duration}ms, Status: Success"
            )
            return result
        except Exception as e:
            end_time = time.time()
            duration = round((end_time - start_time) * 1000, 2)
            logging.error(
                f"Airtable API Request - Model: {model_class}, Method: {method_name}, "
                f"Duration: {duration}ms, Status: Error, Error: {str(e)}"
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