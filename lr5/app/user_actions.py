import csv
from io import BytesIO
from flask import Blueprint, render_template, request, send_file
from app import check_rights
from math import ceil
from utils import check_rights
bp = Blueprint('user_actions', __name__, url_prefix='/user_actions')
MAX_PER_PAGE = 10

from flask_login import login_required
@bp.route('/')

@login_required
def index():
    from flask_login import current_user
    
    from app import db_connector
    page = request.args.get('page', 1, type=int)
    
    user_filter = ""
    if current_user.role_name == 'Пользователь':
        user_filter = f"WHERE visit_logs.user_id = {current_user.id}"
    
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        query = (f"SELECT surname, name, last_name, "
                 f"path, visit_logs.created_at AS created_at "
                 f"FROM visit_logs LEFT JOIN users ON visit_logs.user_id = users.user_id "
                 f"{user_filter} "
                 f"LIMIT {MAX_PER_PAGE} OFFSET {(page - 1) * MAX_PER_PAGE}")
        cursor.execute(query)
        user_actions = cursor.fetchall()

        query = f"SELECT COUNT(*) as count FROM visit_logs {user_filter}"
        cursor.execute(query)
        record_count = cursor.fetchone().count
        page_count = ceil(record_count / MAX_PER_PAGE)
        pages = range(max(1, page - 3), min(page_count, page + 3) + 1)
    
    return render_template("user_actions/index.html", user_actions=user_actions, 
                           page=page, pages=pages, page_count=page_count)


@bp.route('users_stats')
@check_rights('can_stat1')
def users_stats():
    from app import db_connector
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        query = ("SELECT users.user_id, users.name, users.last_name, users.surname, "
         "COUNT(*) AS entries_counter "
         "FROM visit_logs LEFT JOIN users ON visit_logs.user_id = users.user_id "
         "GROUP BY users.user_id")
        cursor.execute(query)
        users_stats = cursor.fetchall()
        
    return render_template("user_actions/users_stats.html", users_stats=users_stats)
@bp.route('paths_stats')
@check_rights('can_stat2')
def paths_stats():
    from app import db_connector
    with db_connector.connect().cursor(named_tuple=True) as cursor:
         query = ("SELECT path, COUNT(*) AS entries_counter from visit_logs group by path")
         cursor.execute(query)
         user_actions = cursor.fetchall()
         print(user_actions)
    return render_template("user_actions/paths_stats.html", user_actions=user_actions)
@bp.route('user_export.csv')

def user_export():
    from app import db_connector
    with db_connector.connect().cursor(named_tuple=True) as cursor:
        query = ("SELECT users.user_id, users.name, users.last_name, users.surname, "
         "COUNT(*) AS entries_counter "
         "FROM visit_logs LEFT JOIN users ON visit_logs.user_id = users.user_id "
         "GROUP BY users.user_id")
        cursor.execute(query)
        print(cursor.statement)
        users_stats = cursor.fetchall()
        result = ''
        fields = ['last_name', 'name', 'surname', 'entries_counter']
        none_values = ['не', 'авторизованный', 'пользователь']
        result += ','.join(fields)+'\n'
        for record in users_stats:
            if record.user_id is None:
                result += ','.join(none_values)+','+str(record.entries_counter)+'\n'
                continue
            result += ','.join([str(getattr(record, field)) for field in fields])+'\n'
    return send_file(BytesIO(result.encode()), as_attachment=True, mimetype='text/csv', download_name='user_export.csv')
        

    