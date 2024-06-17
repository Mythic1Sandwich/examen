# validators.py

import re

def validate_login(login):
    if not login:
        return "Логин не может быть пустым"
    if len(login) < 5:
        return "Логин должен содержать не менее 5 символов"

    return None

def validate_password(password):
    if not password:
        return "Пароль не может быть пустым"
    if len(password) < 8 or len(password) > 128:
        return "Пароль должен содержать от 8 до 128 символов"
    if not any(c.isupper() for c in password) or not any(c.islower() for c in password):
        return "Пароль должен содержать как минимум одну заглавную и одну строчную букву"
    if not any(c.isdigit() for c in password):
        return "Пароль должен содержать как минимум одну цифру"
    if bool(re.search(r"\s", password)):
        return "Пароль не должен содержать пробелов"
    forbidden_chars = "~!@#$%^&*_-+()[]{}><\/|\"\'.,:;"
    if any(char in forbidden_chars for char in password):
        return "Пароль не должен содержать запрещенные символы"
  
    return None

def validate_name(name):
    if not name:
        return "Имя не может быть пустым"

    return None
    

def validate_surname(surname):
    if not surname:
        return "Отчество не может быть пустым"
 
    return None

