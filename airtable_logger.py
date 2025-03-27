import logging
import time
import os
from functools import wraps
from pyairtable.orm import Model

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

def log_airtable_request(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            # Get the model class name and method name
            method_name = func.__name__
            model_class = "Unknown"
            
            # Handle both class methods and instance methods
            if args and isinstance(args[0], Model):
                model_class = args[0].__class__.__name__
            elif args and isinstance(args[0], type) and issubclass(args[0], Model):
                model_class = args[0].__name__
            
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

# Monkey patch the Model class methods to add logging
def patch_model_methods():
    methods_to_patch = [
        'all', 'first', 'get', 'save', 'delete', 'create', 'update'
    ]
    
    for method_name in methods_to_patch:
        if hasattr(Model, method_name):
            original_method = getattr(Model, method_name)
            setattr(Model, method_name, log_airtable_request(original_method))

# Call this function when the module is imported
patch_model_methods() 