
#As attachment /True не False
        #BytesIO
        #Декоратор 
from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from mysqldb import DBConnector
from mysql.connector.errors import DatabaseError
from functools import wraps
from valid import validate_login, validate_password, validate_name, validate_surname
from utils import check_rights  
from user_actions import bp as user_actions_bp

CREATE_USER_FIELDS = ['login', 'password', 'name', 'last_name', 'surname', 'role_id']
EDIT_USER_FIELDS = ['last_name', 'name', 'surname', 'role_id']
CHANGE_PASS_FIELDS=['password','newpass','newpass2']
app = Flask(__name__)
application = app
app.config.from_pyfile('config.py')


db_connector = DBConnector(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth"
login_manager.login_message = "Войдите, чтобы просматривать содержимое данной страницы"
login_manager.login_message_category = "warning"
app.register_blueprint(user_actions_bp)
class User(UserMixin):
    def __init__(self, user_id, login, role_name):
        self.id = user_id
        self.login = login
        self.role_name = role_name

    def is_admin(self):
        return self.role_name == 'Администратор'

    def has_permission(self, action):
        has_perm = action in ROLES_PERMISSIONS.get(self.role_name, [])
        print(f"Пользователь {self.login} с ролью {self.role_name} имеет разрешение {action}: {has_perm}")  # Отладочное сообщение
        return has_perm
    def can_view_user_stats(self):
        return self.has_permission('can_stat1')

    def can_view_path_stats(self):
        return self.has_permission('can_stat2')

ROLES_PERMISSIONS = {
    'Администратор': ['create', 'edit', 'view', 'delete', 'view_log','edit_own','view_own','can_stat1','can_stat2'],
    'Пользователь': ['edit_own', 'view_own', 'view_log_own']
}

def get_roles():
    query = "SELECT * FROM roles"
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query)
        roles = cursor.fetchall()
    return roles

@login_manager.user_loader
def load_user(user_id):
    query = """
    SELECT users.user_id, users.login, roles.role_name 
    FROM users 
    JOIN roles ON users.role_id = roles.role_id 
    WHERE users.user_id = %s
    """
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
    if user:
        print(f"Loaded user: {user.login}, role_name: {user.role_name}")  # Отладочное сообщение
        return User(user.user_id, user.login, user.role_name)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info')
def info():
    session['counter'] = session.get('counter', 0) + 1
    return render_template('info.html')

@app.route('/auth', methods=["GET", "POST"])
def auth():
    if request.method == "GET":
        return render_template("auth.html")
    
    login = request.form.get("login", "")
    password = request.form.get("pass", "")
    remember = request.form.get("remember") == "on"

    query = """
    SELECT users.user_id, users.login, roles.role_name 
    FROM users 
    JOIN roles ON users.role_id = roles.role_id 
    WHERE users.login=%s AND users.password=SHA2(%s, 256)
    """
    
    print(query)

    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (login, password))
        print(cursor.statement)
        user = cursor.fetchone()

    if user:
        login_user(User(user.user_id, user.login, user.role_name), remember=remember)
        flash("Успешная авторизация", category="success")
        target_page = request.args.get("next", url_for("index"))
        return redirect(target_page)

    flash("Введены некорректные учётные данные пользователя", category="danger")    
    return render_template("auth.html")

@app.route('/users')
def users():
    query = 'SELECT users.*, roles.role_name FROM users LEFT JOIN roles ON users.role_id = roles.role_id'
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query)
        data = cursor.fetchall() 
        print(data)
    return render_template("users.html", users=data)

def get_form_data(required_fields):
    user = {}
    for field in required_fields:
        user[field] = request.form.get(field) or None
    return user



@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required

@check_rights('edit_own')
def edit_user(user_id):
    if user_id != current_user.id and not current_user.has_permission('edit'):
        flash('У вас недостаточно прав для редактирования этого профиля.', 'warning')
        return redirect(url_for('index'))
    
    errors = {}
    query = "SELECT users.*, roles.role_name FROM users JOIN roles ON users.role_id = roles.role_id WHERE user_id = %s"
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()

    if request.method == "POST":
        user_data = {field: request.form.get(field) for field in EDIT_USER_FIELDS if field != 'role_id'}
        user_data['user_id'] = user_id

        query = ("UPDATE users SET last_name=%(last_name)s, name=%(name)s, surname=%(surname)s "
                 "WHERE user_id=%(user_id)s")

        try:
            with db_connector.connect().cursor(named_tuple=True) as cursor:
                cursor.execute(query, user_data)
                db_connector.connect().commit()
            
            flash("Запись пользователя успешно обновлена", category="success")
            return redirect(url_for('users'))
        except DatabaseError as error:
            flash(f'Ошибка редактирования пользователя! {error}', category="danger")
            db_connector.connect().rollback()

    roles = get_roles() if current_user.is_admin() else []
    return render_template("edit_user.html", user=user, roles=roles, errors=errors)


@app.route('/users/<int:user_id>/seek', methods=['GET'])
@login_required
@check_rights('view_own')
def seek(user_id):
    if user_id != current_user.id and not current_user.has_permission('view_own'):
        flash('У вас недостаточно прав для просмотра этого профиля.', 'warning')
        return redirect(url_for('index'))

    query = "SELECT users.*, roles.role_name FROM users JOIN roles ON users.role_id = roles.role_id WHERE users.user_id = %s"
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()

    return render_template("seek.html", user=user)


@app.route('/user/<int:user_id>/delete', methods=["POST"])
@login_required
@check_rights('delete')
def delete_user(user_id):
    query1 = "DELETE FROM users WHERE user_id=%s"
    try:
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query1, (user_id, ))
            db_connector.connect().commit() 
        flash("Запись пользователя успешно удалена", category="success")
    except DatabaseError as error:
        flash(f'Ошибка удаления пользователя! {error}', category="danger")
        db_connector.connect().rollback()    
    return redirect(url_for('users'))

@app.route('/users/new', methods=['GET', 'POST'])
@login_required
@check_rights('create')
def create_user():
    user = {}
    roles = get_roles()
    errors = {}  
    if request.method == 'POST':
        user = get_form_data(CREATE_USER_FIELDS)

        errors['login'] = validate_login(user['login'])
        errors['password'] = validate_password(user['password'])
        errors['name'] = validate_name(user['name'])
        errors['surname'] = validate_surname(user['surname'])

        # Удаление ключей с None значениями, чтобы избежать ошибок при рендеринге
        errors = {k: v for k, v in errors.items() if v is not None}

        if errors:
            return render_template("user_form.html", user=user, roles=roles, errors=errors)

        query = ("INSERT INTO users "
                 "(login, password, name, last_name, surname, role_id) "
                 "VALUES (%(login)s, SHA2(%(password)s, 256), "
                 "%(name)s, %(last_name)s, %(surname)s, %(role_id)s)")
        
        try:
            with db_connector.connect().cursor(named_tuple=True) as cursor:
                cursor.execute(query, user)
                db_connector.connect().commit()
            flash("Пользователь успешно создан", category="success")
            return redirect(url_for('users'))
        except DatabaseError as error:
            flash(f'Ошибка создания пользователя: {error}', category="danger")    
            db_connector.connect().rollback()
    return render_template("user_form.html", user=user, roles=roles, errors=errors)

@app.before_request
def record_action():
    if request.endpoint == 'static':
        return
    user_id = current_user.id if current_user.is_authenticated else None
    path = request.path
    connection = db_connector.connect()
    try:
        with connection.cursor(named_tuple=True, buffered=True) as cursor:
            query = "INSERT INTO visit_logs (user_id, path) VALUES (%s, %s)"
            cursor.execute(query, (user_id, path))
            connection.commit()
    except db_connector.errors.DatabaseError as error:
        print(error)
        connection.rollback()
@app.route('/user/<int:user_id>/change', methods=["GET", "POST"])
@login_required
def change_password(user_id):
    errors = {} 
    if request.method == 'POST':
        user = get_form_data(CHANGE_PASS_FIELDS)
     
        query_check_password = "SELECT user_id FROM users WHERE user_id = %s AND password = SHA2(%s, 256)"
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query_check_password, (user_id, user["password"]))
            if not cursor.fetchone():
                flash("Текущий пароль введен неверно", category="danger")
                return redirect(url_for('change_password', user_id=user_id, errors=errors))
        
        if user["newpass"] == user["newpass2"]:
            errors['newpass'] = validate_password(user['newpass'])
            errors['newpass2'] = validate_password(user['newpass2'])
            if errors:
                return render_template("change.html", user=user, errors=errors)
            query_change_password = "UPDATE users SET password = SHA2(%s, 256) WHERE user_id = %s"
            try:
                with db_connector.connect().cursor(named_tuple=True) as cursor:
                    cursor.execute(query_change_password, (user["newpass"], user_id))
                    db_connector.connect().commit()
                    flash("Пароль успешно изменен", category="success")
                    return redirect(url_for('users'))
            except DatabaseError as error:
                flash(f'Ошибка изменения пароля! {error}', category="danger")
                db_connector.connect().rollback() #---
                return redirect(url_for('users'))
            
        else:
            flash("Новые пароли не совпадают", category="danger")
            return redirect(url_for('change_password', user_id=user_id, errors=errors))
    return render_template("change.html", errors=errors)



@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route('/secret')
@login_required
def secret():
    return render_template('secret.html')
