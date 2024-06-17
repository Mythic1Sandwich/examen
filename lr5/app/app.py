
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

CREATE_BOOK_FIELDS = ['book_name', 'book_descr', 'releaser', 'publisher', 'author', 'volume']

CREATE_USER_FIELDS = ['login', 'password','name', 'last_name', 'surname','role_id']
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

class User(UserMixin):
    def __init__(self, user_id, login, role_name):
        self.id = user_id
        self.login = login
        self.role_name = role_name

    def is_admin(self):
        return self.role_name == 'администратор'
    def is_moder(self):
        return self.role_name == 'модератор'
    def is_user(self):
        return self.role_name == 'пользователь'
    def has_permission(self, action):
        has_perm = action in ROLES_PERMISSIONS.get(self.role_name, [])
        print(f"Пользователь {self.login} с ролью {self.role_name} имеет разрешение {action}: {has_perm}")  # Отладочное сообщение
        return has_perm

ROLES_PERMISSIONS = {
    'администратор': ['create', 'edit_book', 'view', 'delete'],
    'пользователь': ['view'],
    'модератор': ['create', 'edit_book', 'view', ]
    
}


def get_roles():
    query = "SELECT * FROM roles"
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query)
        roles = cursor.fetchall()
        print(roles)
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


@app.route('/books')
def books():
    query = '''
        SELECT books.book_id, books.book_name, books.releaser, 
               GROUP_CONCAT(DISTINCT genre_info.genre_descr ORDER BY genre_info.genre_descr ASC) AS all_genres, 
               COALESCE(AVG(reviews.rate), 0) AS avg_rating, 
               (SELECT COUNT(*) from reviews WHERE reviews.book_id = books.book_id) AS num_ratings
        FROM books 
        LEFT JOIN book_genre ON books.book_id = book_genre.book_id
        LEFT JOIN genre_info ON book_genre.genre_id = genre_info.genre_id
        LEFT JOIN reviews ON books.book_id = reviews.book_id
        GROUP BY books.book_id, books.book_name, books.releaser
    '''
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        cursor.execute(query)
        data = cursor.fetchall()
        print(data) 
    return render_template("books.html", books=data)


@app.route('/books/new', methods=['GET', 'POST'])
@login_required
@check_rights('create_book')
def create_book():
    genres = get_genre_name()
    book = {}
    
    if request.method == 'POST':
        book = get_form_data(CREATE_BOOK_FIELDS)
        selected_genres = request.form.getlist('genres')  
        
        insert_book_query = ("INSERT INTO books "
                             "(book_id, book_name, book_descr, releaser, publisher, author, volume) "
                             "VALUES (%(book_id)s, %(book_name)s, %(book_descr)s, "
                             "%(releaser)s, %(publisher)s, %(author)s, %(volume)s)")
        
        get_max_book_id_query = "SELECT MAX(book_id) + 1 AS next_book_id FROM books"
        
        try:
            with db_connector.connect() as connection:
                with connection.cursor(dictionary=True) as cursor:
                    cursor.execute(get_max_book_id_query)
                    next_book_id = cursor.fetchone()['next_book_id']
                    
                    book['book_id'] = next_book_id
                    cursor.execute(insert_book_query, book)
                    connection.commit()
                    
                    if selected_genres:
                        existing_genre_ids = [genre['genre_id'] for genre in genres]
                        selected_genres = [int(genre_id) for genre_id in selected_genres if int(genre_id) in existing_genre_ids]
                        
                        if selected_genres:
                            insert_genre_query = "INSERT INTO book_genre (book_id, genre_id) VALUES (%s, %s)"
                            cursor.executemany(insert_genre_query, [(next_book_id, genre_id) for genre_id in selected_genres])
                            connection.commit()
                    
            flash("Книга успешно создана", category="success")
            return redirect(url_for('books'))
        
        except DatabaseError as error:
            flash(f'Ошибка создания книги: {error}', category="danger")
            db_connector.connect().rollback()
    
    return render_template("book_form.html", book=book, genres=genres)
@app.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@login_required
@check_rights('edit_book')
def edit_book(book_id):
    genres = get_genre_name()

    query_book = """
        SELECT book_id, book_name, book_descr, releaser, publisher, author, volume
        FROM books WHERE book_id = %s
    """
    query_genres = """
        SELECT genre_id FROM book_genre WHERE book_id = %s
    """

    with db_connector.connect().cursor(dictionary=True) as cursor:
        try:
            cursor.execute(query_book, (book_id,))
            book = cursor.fetchone()

            if not book:
                flash(f'Книга с ID {book_id} не найдена', category="danger")
                return redirect(url_for('books'))

            cursor.execute(query_genres, (book_id,))
            existing_genres = [genre['genre_id'] for genre in cursor.fetchall()]

        except DatabaseError as error:
            flash(f'Ошибка при выполнении запроса к базе данных: {error}', category="danger")
            return redirect(url_for('books'))

    if request.method == 'POST':
        updated_book = get_form_data(CREATE_BOOK_FIELDS)
        selected_genres = request.form.getlist('genres')  

        update_book_query = """
            UPDATE books SET
            book_name = %(book_name)s,
            book_descr = %(book_descr)s,
            releaser = %(releaser)s,
            publisher = %(publisher)s,
            author = %(author)s,
            volume = %(volume)s
            WHERE book_id = %(book_id)s
        """
        update_genre_query = """
            INSERT INTO book_genre (book_id, genre_id) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE book_id = VALUES(book_id), genre_id = VALUES(genre_id)
        """
        delete_genre_query = "DELETE FROM book_genre WHERE book_id = %s AND genre_id = %s"

        try:
            with db_connector.connect() as connection:
                with connection.cursor() as cursor:
                    updated_book['book_id'] = book_id
                    cursor.execute(update_book_query, updated_book)
                    cursor.execute("DELETE FROM book_genre WHERE book_id = %s", (book_id,))
                    if selected_genres:
                        cursor.executemany(update_genre_query, [(book_id, int(genre_id)) for genre_id in selected_genres])

                connection.commit()
                flash("Книга успешно обновлена", category="success")
                return redirect(url_for('books'))

        except DatabaseError as error:
            flash(f'Ошибка обновления книги: {error}', category="danger")
            return redirect(url_for('books'))

    return render_template("edit_book.html", action='edit_book', book=book, genres=genres, existing_genres=existing_genres)


def get_genre_name():
    query = '''
        SELECT genre_info.genre_id, genre_info.genre_descr FROM genre_info
    '''
    with db_connector.connect().cursor(dictionary=True) as cursor:
        cursor.execute(query)
        genres = cursor.fetchall()
    return genres




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
def create_user():
    user = {}
    roles = get_roles()
    if request.method == 'POST':
        user = get_form_data(CREATE_USER_FIELDS)

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
    return render_template("user_form.html", user=user, roles=roles)



@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route('/secret')
@login_required
def secret():
    return render_template('secret.html')
