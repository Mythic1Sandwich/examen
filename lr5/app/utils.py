from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def check_rights(action):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id')
            if not current_user.has_permission(action):
                if action.endswith('_own') and user_id == current_user.id:
                    return function(*args, **kwargs)
                elif not action.endswith('_own') and current_user.has_permission(action.split('_')[0]):
                    return function(*args, **kwargs)
                flash('У вас недостаточно прав для доступа к данной странице.', 'warning')
                return redirect(url_for('index'))
            return function(*args, **kwargs)
        return wrapper
    return decorator
